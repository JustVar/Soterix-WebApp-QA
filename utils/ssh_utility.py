import paramiko

class SSHUtility:
    def __init__(self, hostname, username, password=None, key_filename=None, port=22):
        """
        Initialize the SSH utility.

        :param hostname: The IP address or hostname of the server.
        :param username: The username to authenticate with.
        :param password: The password for authentication (optional if using SSH keys).
        :param key_filename: The path to the private key for SSH authentication (optional if using password).
        :param port: The port for SSH connection (default is 22).
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.ssh_client = paramiko.SSHClient()

        # Automatically add the server's SSH key
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        """
        Establish SSH connection using either password or SSH key.
        """
        try:
            if self.password:
                self.ssh_client.connect(self.hostname, username=self.username, password=self.password, port=self.port)
            elif self.key_filename:
                self.ssh_client.connect(self.hostname, username=self.username, key_filename=self.key_filename, port=self.port)
            else:
                raise ValueError("Either password or key_filename must be provided.")

            print(f"Successfully connected to {self.hostname}")
        except Exception as e:
            print(f"Failed to connect: {e}")

    def run_command(self, command):
        """
        Run a command on the remote server via SSH.

        :param command: The command to execute.
        :return: A tuple of stdout and stderr output.
        """
        try:
            self.connect()
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            # Get the command output
            out = stdout.read().decode()
            err = stderr.read().decode()
            self.close()
            return out, err
        except Exception as e:
            print(f"Failed to run command: {e}")
            return "", str(e)

    def run_sudo_command(self, command, sudo_password=None):
        """
        Run a command with sudo privileges on the remote server.

        :param command: The command to execute with sudo.
        :param sudo_password: The password to use with sudo (optional).
        :return: A tuple of stdout and stderr output.
        """
        if sudo_password:
            command = f"echo {sudo_password} | sudo -S {command}"
        return self.run_command(command)

    def close(self):
        """
        Close the SSH connection.
        """
        self.ssh_client.close()
        print("SSH connection closed.")

