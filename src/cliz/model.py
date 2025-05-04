import subprocess
from typing import Dict, Optional


class CommandLineTool:
    """Represents a command-line tool that can be executed.
    
    This class provides a wrapper around command-line tools, handling execution,
    help commands, and formatting.
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
    ) -> None:
        """Initialize a new CommandLineTool.
        
        Args:
            name: The name of the command-line tool
            description: A short description of what the tool does
        """
        self.name = name
        self.description = description

    def to_dict(self) -> Dict[str, str]:
        """Convert the tool to a dictionary representation.
        
        Returns:
            A dictionary containing the tool's name and description
        """
        return {
            "name": self.name,
            "description": self.description,
        }

    def help(self, sub_command: Optional[str] = None, help_arg: str = "-h") -> str:
        """Get help information for this tool.
        
        Args:
            sub_command: Optional sub-command to get help for
            help_arg: The argument to pass to get help
            
        Returns:
            str: The help output.
        """
        args = f"{sub_command} {help_arg}" if sub_command else help_arg
        return self.execute(args)
    
    def execute(self, args: str, work_dir: str = ".") -> str:
        """Execute the command-line tool.
        
        Args:
            args: Arguments to pass to the command
            work_dir: Working directory for the command
            
        Returns:
            str: The output of the command.
        """
        command = self.name
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
