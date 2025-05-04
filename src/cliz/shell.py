import subprocess
import sys
from typing import Dict, List, Optional, Tuple


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
    
    def _truncate_output(self, lines: List[str], tail_lines: int = 100) -> str:
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
            lines = lines[-tail_lines:]
            
            output = f'''...(truncated {len(lines)} lines)...
            {lines}
            '''
            
            return output.strip()

    
    def execute(self, 
            command: str, 
            args: str,
            work_dir: str = ".", 
            stream_output: bool = False) -> str:
        """Execute the command-line tool.
        
        Args:
            command: The command to execute
            args: Arguments to pass to the command
            work_dir: Working directory for the command
            stream_output: Whether to stream output in real-time and print to terminal
            
        Returns:
            str: The output of the command.
        """
        full_command = f"{command} {args}"

        try:
            # Create process
            process = subprocess.Popen(
                full_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=work_dir,
                universal_newlines=True
            )
            
            output_lines = []
            error_lines = []
            
            if stream_output:
                # Stream output in real-time and print to terminal
                while True:
                    # Check stdout
                    stdout_line = process.stdout.readline()
                    if stdout_line:
                        print(stdout_line, end='')
                        output_lines.append(stdout_line)
                    
                    # Check stderr
                    stderr_line = process.stderr.readline()
                    if stderr_line:
                        print(stderr_line, end='', file=sys.stderr)
                        error_lines.append(stderr_line)
                    
                    # Check if process has terminated
                    if process.poll() is not None:
                        # Read any remaining output
                        for line in process.stdout:
                            print(line, end='')
                            output_lines.append(line)
                        
                        for line in process.stderr:
                            print(line, end='', file=sys.stderr)
                            error_lines.append(line)
                        break
            else:
                # Silently wait for process to complete and collect all output
                stdout, stderr = process.communicate()
                
                if stdout:
                    output_lines.append(stdout)
                
                if stderr:
                    error_lines.append(stderr)
            
            # Determine final output based on return code
            returncode = process.poll()
       
            if returncode == 0:
                return self._truncate_output(output_lines)
            else:
                error_output = self._truncate_output(error_lines)
                return f"Error: {error_output}"
                
        except Exception as e:
            error_message = f"Error: {str(e)}"
            if stream_output:
                print(error_message, file=sys.stderr)
            return error_message
