from typing import List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

class ServerConfig:
    def __init__(self, name: str, ip: str, user: str, password: str):
        self.name = name
        self.ip = ip
        self.user = user
        self.password = password

def load_server_configs() -> List[ServerConfig]:
    """Load server configurations from environment variables"""
    servers = []
    
    # Get the number of servers from environment variable
    num_servers = int(os.getenv('NUM_SERVERS', '1'))
    
    for i in range(1, num_servers + 1):
        name = os.getenv(f'SERVER_{i}_NAME')
        ip = os.getenv(f'SERVER_{i}_IP')
        user = os.getenv(f'SERVER_{i}_USER')
        password = os.getenv(f'SERVER_{i}_PASSWORD')
        
        if name and ip and user and password:
            servers.append(ServerConfig(name, ip, user, password))
    
    return servers

def get_teams_webhook() -> str:
    """Get Teams webhook URL from environment variables"""
    return os.getenv('TEAMS_WEBHOOK_URL', '')
