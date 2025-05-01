import subprocess
from typing import Dict, Optional

from pydantic import BaseModel, Field


class CommandResult(BaseModel):
    """Result of a command execution.
    
    Attributes:
        success: Whether the command executed successfully
        stdout: The standard output from the command
        stderr: The standard error from the command
    """
    success: bool
    stdout: str
    stderr: str


class CommandLineTool:
    """Represents a command-line tool that can be executed.
    
    This class provides a wrapper around command-line tools, handling execution,
    help commands, and formatting.
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        help_arg: str = "-h"
    ) -> None:
        """Initialize a new CommandLineTool.
        
        Args:
            name: The name of the command-line tool
            description: A short description of what the tool does
            help_arg: The argument to pass to get help information
        """
        self.name = name
        self.description = description
        self.help_arg = help_arg

    def to_dict(self) -> Dict[str, str]:
        """Convert the tool to a dictionary representation.
        
        Returns:
            A dictionary containing the tool's name and description
        """
        return {
            "name": self.name,
            "description": self.description,
        }

    def help(self, sub_command: Optional[str] = None) -> CommandResult:
        """Get help information for this tool.
        
        Args:
            sub_command: Optional sub-command to get help for
            
        Returns:
            CommandResult containing the help output
        """
        args = f"{sub_command} {self.help_arg}" if sub_command else self.help_arg
        return self.execute(args)
    
    def execute(self, args: str, work_dir: str = ".") -> CommandResult:
        """Execute the command-line tool.
        
        Args:
            args: Arguments to pass to the command
            work_dir: Working directory for the command
            
        Returns:
            CommandResult containing execution output and status
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
            success = proc.returncode == 0
            return CommandResult(
                success=success, 
                stdout=proc.stdout, 
                stderr=proc.stderr
            )
        
        except Exception as e:
            return CommandResult(
                success=False, 
                stdout="", 
                stderr=str(e)
            )