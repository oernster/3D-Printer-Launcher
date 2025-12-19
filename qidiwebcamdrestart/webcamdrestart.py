import paramiko
import time

def ssh_command(ip, username, password, command):
    # Create a new SSH client
    client = paramiko.SSHClient()
    # Automatically add host keys from the system host keys
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Connect to the SSH server
        client.connect(ip, username=username, password=password)
        # Start an interactive shell session
        ssh_session = client.invoke_shell()
        
        # Wait for the prompt
        time.sleep(1)
        
        # Send the command
        ssh_session.send(command + "\n")
        time.sleep(1)  # Wait for the command to execute
        
        # Send the exit command
        ssh_session.send("exit\n")
        time.sleep(0.5)
        
        # Receive the output
        output = ssh_session.recv(5000).decode()
        print(output)
        
    finally:
        # Close the connection
        client.close()

# User settings
ip_address = "192.168.1.120"
username = "root"
password = "Crust:2024"  # Replace with your actual password

# Commands to execute
commands = "sudo service webcamd restart"

# Run the SSH command function
ssh_command(ip_address, username, password, commands)
