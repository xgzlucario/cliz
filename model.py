from pydantic import BaseModel
from typing import Optional
import subprocess

class Result(BaseModel):
    success: bool
    stdout: str
    stderr: str

class Tool:
    def __init__(self,
        name: str,
        description: str = "",
        help_arg: str = "-h",
        is_uv_tool: bool = False):
        
        self.name = name
        self.description = description
        self.help_arg = help_arg
        self.is_uv_tool = is_uv_tool

    def __dict__(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
        }

    def help(self, sub_command: Optional[str] = None) -> Result:
        args = f"{sub_command} {self.help_arg}" if sub_command else self.help_arg
        
        return self.execute(args)
    
    def execute(self, args: str, work_dir: str = ".") -> Result:
        command = self.name

        if self.is_uv_tool:
            full_command = f"uv run {command} {args}"
        else:
            full_command = f"{command} {args}"

        try:
            proc = subprocess.run(full_command, capture_output=True, text=True, check=False, cwd=work_dir, shell=True)
            success = proc.returncode == 0
            return Result(success=success, stdout=proc.stdout, stderr=proc.stderr)
        
        except Exception as e:
            return Result(success=False, stdout="", stderr=str(e))