import subprocess
import logging
from typing import Dict, Any, List
import re
from datetime import datetime
import time
from functools import lru_cache

logger = logging.getLogger(__name__)

class IPMIMonitor:
    def __init__(self, server_config: 'ServerConfig'):
        self.server_config = server_config
        self.ipmi_user = server_config.user
        self.ipmi_password = server_config.password
        self.ipmi_host = server_config.ip
        self.name = server_config.name
        self.vendor = self._detect_vendor()
        self.alert_history = []  # Store alert history
        self._last_update = 0
        self._cache = {}
        logger.info(f"Initialized IPMI monitor for {self.name} ({self.ipmi_host})")

    def _is_cache_valid(self, key: str, timeout: int = 30) -> bool:
        """Check if cached value is still valid"""
        if key not in self._cache:
            return False
        return time.time() - self._cache[key]['timestamp'] < timeout

    def _cache_result(self, key: str, value: Any, timeout: int = 30) -> None:
        """Cache a result with timestamp"""
        self._cache[key] = {
            'value': value,
            'timestamp': time.time()
        }

    def _get_cached_result(self, key: str) -> Any:
        """Get cached result if valid"""
        if self._is_cache_valid(key):
            logger.debug(f"Cache hit for {key}")
            return self._cache[key]['value']
        logger.debug(f"Cache miss for {key}")
        return None

    @lru_cache(maxsize=128)
    def _run_ipmi_command(self, command: str) -> str:
        """Run an IPMI command and return the output"""
        try:
            cmd = f"ipmitool -I lanplus -H {self.ipmi_host} -U {self.ipmi_user} -P {self.ipmi_password} {command}"
            logger.debug(f"Executing IPMI command: {cmd}")
            start_time = time.time()
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            duration = time.time() - start_time
            logger.debug(f"IPMI command executed in {duration:.2f} seconds")
            logger.debug(f"IPMI command output: {result.stdout}")
            logger.debug(f"IPMI command error: {result.stderr}")
            
            if result.returncode != 0:
                logger.error(f"IPMI command failed with exit code {result.returncode}: {result.stderr}")
                return ""
            
            if not result.stdout.strip():
                logger.warning(f"IPMI command returned empty output: {cmd}")
                return ""
            
            return result.stdout
        except Exception as e:
            logger.error(f"Error running IPMI command: {str(e)}")
            return ""

    def _detect_vendor(self) -> str:
        """Detect server vendor using IPMI"""
        try:
            # Get system information
            system_info = self._run_ipmi_command("fru print 0")
            
            # Check for vendor specific strings
            if "HP" in system_info or "HPE" in system_info:
                self.server_name = "HP" + self._extract_model(system_info)
                return "HP"
            elif "Dell" in system_info:
                self.server_name = "Dell" + self._extract_model(system_info)
                return "Dell"
            elif "Lenovo" in system_info:
                self.server_name = "Lenovo" + self._extract_model(system_info)
                return "Lenovo"
            else:
                return "Unknown"
        except Exception as e:
            logger.error(f"Error detecting vendor: {str(e)}")
            return "Unknown"

    def _extract_model(self, system_info: str) -> str:
        """Extract server model from system information"""
        try:
            for line in system_info.split('\n'):
                if 'Product Name' in line:
                    return line.split(':')[1].strip()
            return ""
        except Exception as e:
            logger.error(f"Error extracting model: {str(e)}")
            return ""

    def get_alert_history(self) -> List[Dict[str, Any]]:
        """Get alert history"""
        return self.alert_history[-10:]  # Return last 10 alerts

    def _add_alert(self, message: str, severity: str):
        """Add an alert to the history"""
        try:
            alert = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message': message,
                'severity': severity,
                'server': self.name
            }
            self.alert_history.append(alert)
            if len(self.alert_history) > 100:  # Keep only last 100 alerts
                self.alert_history.pop(0)
        except Exception as e:
            logger.error(f"Error adding alert: {str(e)}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the server"""
        try:
            # Check cache first
            cached = self._get_cached_result('health_status')
            if cached:
                return cached
                
            # Get chassis status
            chassis_status = self._run_ipmi_command('chassis status')
            
            # Get system event log
            sel_log = self._run_ipmi_command('sel elist')
            
            # Get motherboard status
            motherboard_status = self._run_ipmi_command('fru print 0')
            
            # Parse chassis status
            status = {
                'overall_status': 'OK',
                'motherboard_status': 'OK',
                'chassis_status': {},
                'sel_log': []
            }
            
            # Check chassis status
            if 'Chassis Power is on' not in chassis_status:
                status['overall_status'] = 'Critical'
                self._add_alert('Chassis power is off', 'Critical')
            
            # Check SEL log for critical events
            if sel_log:
                for line in sel_log.split('\n'):
                    if 'Critical' in line:
                        status['overall_status'] = 'Critical'
                        self._add_alert(f'SEL log contains critical event: {line}', 'Critical')
                    elif 'Warning' in line:
                        status['overall_status'] = 'Warning'
                        self._add_alert(f'SEL log contains warning event: {line}', 'Warning')
            
            # Check motherboard status
            if 'FRU Device Description' in motherboard_status:
                status['motherboard_status'] = 'OK'
            else:
                status['motherboard_status'] = 'Critical'
                status['overall_status'] = 'Critical'
                self._add_alert('Motherboard FRU information not available', 'Critical')
            
            # Add chassis status details
            for line in chassis_status.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    status['chassis_status'][key.strip()] = value.strip()
            
            # Cache the result
            self._cache_result('health_status', status)
                except Exception as e:
                    logger.error(f"Error parsing sensor: {str(e)}")
                    continue
            
            return status
        except Exception as e:
            logger.error(f"Error in get_health_status: {str(e)}")
            return {'overall_status': 'Unknown', 'components': {}, 'motherboard_status': 'Unknown'}

    def get_power_status(self) -> Dict[str, Any]:
        """Get power supply status"""
        status = {
            'power_supplies': [],
            'status': 'OK'
        }
        
        # Get power supply readings
        power = self._run_ipmi_command("sdr type Power")
        
        for line in power.split('\n'):
            if not line.strip():
                continue
            
            try:
                parts = line.split('|')
                if len(parts) < 3:
                    continue
                
                sensor_name = parts[0].strip()
                reading = parts[1].strip()
                status_text = parts[2].strip()
                
                if 'PS' in sensor_name:
                    status['power_supplies'].append({
                        'name': sensor_name,
                        'reading': reading,
                        'status': status_text
                    })
                    
                    if 'fail' in status_text.lower():
                        status['status'] = 'Critical'
            except Exception as e:
                logger.error(f"Error parsing power supply: {str(e)}")
                continue
        
        return status

    def get_temperature_status(self) -> Dict[str, Any]:
        """Get temperature readings"""
        status = {
            'temperatures': [],
            'status': 'OK'
        }
        
        # Get temperature readings
        temp = self._run_ipmi_command("sdr type Temperature")
        
        for line in temp.split('\n'):
            if not line.strip():
                continue
            
            try:
                parts = line.split('|')
                if len(parts) < 3:
                    continue
                
                sensor_name = parts[0].strip()
                reading = parts[1].strip()
                status_text = parts[2].strip()
                
                # Extract temperature value
                temp_value = float(re.search(r'\d+\.?\d*', reading).group())
                
                status['temperatures'].append({
                    'name': sensor_name,
                    'temperature': temp_value,
                    'status': status_text
                })
                
                # Check for high temperatures
                if temp_value > 80:  # Critical threshold
                    status['status'] = 'Critical'
                elif temp_value > 70:  # Warning threshold
                    status['status'] = 'Warning'
            except Exception as e:
                logger.error(f"Error parsing temperature: {str(e)}")
                continue
        
        return status

    def get_fan_status(self) -> Dict[str, Any]:
        """Get fan status"""
        status = {
            'fans': [],
            'status': 'OK'
        }
        
        # Get fan readings
        fans = self._run_ipmi_command("sdr type Fan")
        
        for line in fans.split('\n'):
            if not line.strip():
                continue
            
            try:
                parts = line.split('|')
                if len(parts) < 3:
                    continue
                
                sensor_name = parts[0].strip()
                reading = parts[1].strip()
                status_text = parts[2].strip()
                
                if 'Fan' in sensor_name:
                    status['fans'].append({
                        'name': sensor_name,
                        'reading': reading,
                        'status': status_text
                    })
                    
                    if 'fail' in status_text.lower():
                        status['status'] = 'Critical'
            except Exception as e:
                logger.error(f"Error parsing fan: {str(e)}")
                continue
        
        return status

    def get_memory_status(self) -> Dict[str, Any]:
        """Get memory status"""
        status = {
            'memory_modules': [],
            'status': 'OK'
        }
        
        # Get memory readings
        memory = self._run_ipmi_command("sdr type Memory")
        
        for line in memory.split('\n'):
            if not line.strip():
                continue
            
            try:
                parts = line.split('|')
                if len(parts) < 3:
                    continue
                
                sensor_name = parts[0].strip()
                reading = parts[1].strip()
                status_text = parts[2].strip()
                
                if 'DIMM' in sensor_name or 'Memory' in sensor_name:
                    status['memory_modules'].append({
                        'name': sensor_name,
                        'reading': reading,
                        'status': status_text
                    })
                    
                    if 'fail' in status_text.lower():
                        status['status'] = 'Critical'
            except Exception as e:
                logger.error(f"Error parsing memory: {str(e)}")
                continue
        
        return status

    def get_storage_status(self) -> Dict[str, Any]:
        """Get storage status"""
        status = {
            'drives': [],
            'status': 'OK'
        }
        
        # Get storage readings
        storage = self._run_ipmi_command("sdr type Storage")
        
        for line in storage.split('\n'):
            if not line.strip():
                continue
            
            try:
                parts = line.split('|')
                if len(parts) < 3:
                    continue
                
                sensor_name = parts[0].strip()
                reading = parts[1].strip()
                status_text = parts[2].strip()
                
                if 'Drive' in sensor_name or 'Disk' in sensor_name:
                    status['drives'].append({
                        'name': sensor_name,
                        'reading': reading,
                        'status': status_text
                    })
                    
                    if 'fail' in status_text.lower():
                        status['status'] = 'Critical'
            except Exception as e:
                logger.error(f"Error parsing storage: {str(e)}")
                continue
        
        return status

    def get_system_info(self) -> Dict[str, Any]:
        """Get system information including IP address"""
        info = {
            'manufacturer': '',
            'model': '',
            'serial_number': '',
            'firmware_version': '',
            'ip_address': self.ipmi_host,
            'server_name': ''
        }
        
        # Get system information
        fru = self._run_ipmi_command("fru")
        
        for line in fru.split('\n'):
            if not line.strip():
                continue
            
            try:
                if 'Manufacturer' in line:
                    info['manufacturer'] = line.split('Manufacturer : ')[1].strip()
                elif 'Product Name' in line:
                    info['model'] = line.split('Product Name : ')[1].strip()
                elif 'Serial Number' in line:
                    info['serial_number'] = line.split('Serial Number : ')[1].strip()
            except Exception as e:
                logger.error(f"Error parsing FRU: {str(e)}")
                continue
        
        # Get firmware version
        firmware = self._run_ipmi_command("mc info")
        for line in firmware.split('\n'):
            if 'Firmware Revision' in line:
                info['firmware_version'] = line.split('Firmware Revision : ')[1].strip()
                break
        
        return info
