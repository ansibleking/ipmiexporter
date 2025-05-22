from flask import Flask, render_template, jsonify
import os
from datetime import datetime
import pymsteams
from dotenv import load_dotenv
import logging
import subprocess
from config import load_server_configs, get_teams_webhook
from ipmi_monitor import IPMIMonitor

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/metrics')
def metrics():
    return jsonify(get_ipmi_metrics())

@app.route('/test-ipmi/<server_name>')
def test_ipmi(server_name):
    """Test IPMI connection for a specific server"""
    try:
        # Load server configurations
        servers = load_server_configs()
        if server_name not in [server.name for server in servers]:
            return jsonify({
                'error': f'Server {server_name} not found'
            }), 404
        
        # Initialize IPMI monitor for this server
        server = next((s for s in servers if s.name == server_name), None)
        if not server:
            return jsonify({
                'error': 'Server configuration not found'
            }), 500
            
        monitor = IPMIMonitor(server)
        
        # Test basic IPMI connection
        result = monitor._run_ipmi_command('mc info')
        if not result:
            return jsonify({
                'error': 'Failed to connect to IPMI interface'
            }), 500
            
        # Test health status
        health = monitor.get_health_status()
        
        return jsonify({
            'success': True,
            'health': health,
            'ipmi_info': result
        })
    except Exception as e:
        logger.error(f"Error testing IPMI for {server_name}: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

# Initialize Teams notifier
teams_webhook = get_teams_webhook()
teams_notifier = None
if teams_webhook:
    teams_notifier = pymsteams.connectorcard(teams_webhook)

# Load server configurations and initialize monitors
servers = load_server_configs()
ipmi_monitors = {
    server.name: IPMIMonitor(server)
    for server in servers
}
        
    def send_alert(self, title, message, severity='warning'):
        if not self.webhook_url:
            logger.warning("Teams webhook URL not configured")
            return
            
        teams_message = pymsteams.connectorcard(self.webhook_url)
        teams_message.title(title)
        teams_message.text(message)
        
        if severity == 'critical':
            teams_message.color("red")
        elif severity == 'warning':
            teams_message.color("yellow")
        else:
            teams_message.color("green")
            
        teams_message.send()
        logger.info(f"Sent Teams notification: {title}")

teams_notifier = TeamsNotifier()

def check_cpu_health():
    cpu_info = cpuinfo.get_cpu_info()
    cpu_temp = psutil.sensors_temperatures().get('coretemp', [])[0].current if hasattr(psutil, 'sensors_temperatures') else None
    cpu_usage = psutil.cpu_percent(interval=1)
    
    metrics = {
        'info': cpu_info,
        'usage': cpu_usage,
        'temperature': cpu_temp
    }
    
    if cpu_temp and cpu_temp > 80:
        teams_notifier.send_alert(
            "CPU Overheating Alert",
            f"CPU temperature reached {cpu_temp}°C",
            'critical'
        )
    
    if cpu_usage > 90:
        teams_notifier.send_alert(
            "High CPU Usage Alert",
            f"CPU usage is at {cpu_usage}%",
            'critical'
        )
    
    return metrics

def check_memory_health():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    metrics = {
        'total': mem.total,
        'used': mem.used,
        'percent': mem.percent,
        'swap_total': swap.total,
        'swap_used': swap.used,
        'swap_percent': swap.percent
    }
    
    if mem.percent > 90:
        teams_notifier.send_alert(
            "High Memory Usage Alert",
            f"Memory usage is at {mem.percent}%",
            'critical'
        )
    
    if swap.percent > 50:
        teams_notifier.send_alert(
            "High Swap Usage Alert",
            f"Swap usage is at {swap.percent}%",
            'warning'
        )
    
    return metrics

def get_ipmi_metrics():
    """Get metrics for all servers"""
    metrics = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'servers': {}
    }
    
    for server_name, monitor in ipmi_monitors.items():
        try:
            server_metrics = {
                'health': monitor.get_health_status(),
                'power': monitor.get_power_status(),
                'temperature': monitor.get_temperature_status(),
                'fans': monitor.get_fan_status(),
                'memory': monitor.get_memory_status(),
                'storage': monitor.get_storage_status(),
                'system_info': monitor.get_system_info(),
                'alert_history': monitor.get_alert_history()
            }
            
            # Check health status and send alerts if needed
            health_status = server_metrics['health']
            if health_status['overall_status'] == 'Critical':
                if teams_notifier:
                    teams_notifier.title(f"Critical IPMI Alert - {server_name}")
                    teams_notifier.text(f"Server {server_name} has critical issues")
                    teams_notifier.color("red")
                    teams_notifier.send()
            elif health_status['overall_status'] == 'Warning':
                if teams_notifier:
                    teams_notifier.title(f"Warning IPMI Alert - {server_name}")
                    teams_notifier.text(f"Server {server_name} has warning conditions")
                    teams_notifier.color("yellow")
                    teams_notifier.send()
            
            metrics['servers'][server_name] = server_metrics
        except Exception as e:
            logger.error(f"Error getting metrics for {server_name}: {str(e)}")
            metrics['servers'][server_name] = {
                'error': str(e)
            }
    
    return metrics

@app.route('/')
@app.route('/index')
@app.route('/dashboard')
def dashboard():
    return render_template('index.html')

@app.route('/metrics')
def metrics():
    return jsonify(get_ipmi_metrics())

if __name__ == '__main__':
    # Check if IPMI tools are installed
    try:
        subprocess.run(['ipmitool', '-V'], capture_output=True)
    except FileNotFoundError:
        logger.error("IPMI tools are not installed. Please install ipmitool.")
        
    app.run(host='0.0.0.0', port=5000, debug=True)
