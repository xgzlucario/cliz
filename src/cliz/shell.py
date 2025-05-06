import subprocess
import tempfile
from typing import List, Optional


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
    
    def truncate_output(self, lines: List[str], tail_lines: int = 30) -> str:
        """Truncate output lines and add notification if necessary.
        
        Args:
            lines: List of output lines
            tail_lines: Maximum number of lines to keep
            
        Returns:
            str: The possibly truncated output with notification
        """
        
        if len(lines) <= tail_lines:
            return ''.join(lines)
        
        else:
            nums_truncated = len(lines) - tail_lines
            lines = lines[-tail_lines:]
            
            output = f'''...(truncated {nums_truncated} lines)...
            {lines}
            '''
            
            return output.strip()

    
    def run(self, command: str, args: str, work_dir: str = ".") -> str:
        """Run a shell command with the given arguments.
        
        Args:
            command: The command to execute
            args: Arguments to pass to the command
            work_dir: Working directory for the command
            
        Returns:
            str: The output of the command.
        """
        full_command = f"{command} {args}"

        try:
            process = subprocess.run(
                full_command,
                shell=True,
                text=True,
                capture_output=True,
                cwd=work_dir
            )

            if process.returncode == 0:
                return process.stdout
            else:
                return f"Error: {process.stderr}"
                
        except Exception as e:
            return f"Error: {str(e)}"
        
    
    def run_background(self, command: str, args: str, work_dir: str = ".") -> dict:
        """Run a shell command with the given arguments in the background.
        
        Args:
            command: The command to execute
            args: Arguments to pass to the command
            work_dir: Working directory for the command
            
        Returns:
            dict: Process information including the path to output file.
        """
        full_command = f"{command} {args}"
        
        try:
            # create a temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix='.log')
            temp_file_path = temp_file.name
            temp_file.close()
            
            # redirect output to the temp file
            with open(temp_file_path, 'w') as output_file:
                process = subprocess.Popen(
                    full_command,
                    shell=True,
                    cwd=work_dir,
                    stdout=output_file,
                    stderr=output_file
                )

            return {
                "pid": process.pid,
                "cwd": work_dir,
                "command": full_command,
                "output_file": temp_file_path
            }

        except Exception as e:                    
            return {
                "error": str(e)
            }
