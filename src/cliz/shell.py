import subprocess
from typing import Dict, Optional


class ShellToolkit:
    """Represents a shell toolkit that can be executed.
    
    This class provides a wrapper around shell commands, handling execution,
    help commands, and formatting.
    """
    
    def help(self, command: str, sub_command: Optional[str] = None, help_arg: str = "-h") -> str:
        """Get help information for this tool.
        
        Args:
            command: The command to get help for
            sub_command: Optional sub-command to get help for
            help_arg: The argument to pass to get help
            
        Returns:
            str: The help output.
        """
        args = f"{sub_command} {help_arg}" if sub_command else help_arg
        return self.execute(command, args)
    
    def execute(self, command: str, args: str, work_dir: str = ".") -> str:
        """Execute the command-line tool.
        
        Args:
            command: The command to execute
            args: Arguments to pass to the command
            work_dir: Working directory for the command
            
        Returns:
            str: The output of the command.
        """
        full_command = f"{command} {args}"

        try:
            proc = subprocess.run(
                full_command, 
                capture_output=True, 
                text=True,
                check=False, 
                cwd=work_dir, 
                shell=True
            )
            if proc.returncode == 0:
                return proc.stdout
            else:
                return f"Error: {proc.stderr}"
                
        except Exception as e:
            return f"Error: {str(e)}"
