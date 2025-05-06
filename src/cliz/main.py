import argparse
import logging
import os
import platform
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Optional

import html2text
import httpx
import yaml
from agno.agent import Agent
from agno.exceptions import StopAgentRun
from agno.models.openai.like import OpenAILike
from agno.storage.sqlite import SqliteStorage
from agno.tools import FunctionCall, tool
from agno.tools.thinking import ThinkingTools
from rich.console import Console
from rich.prompt import Prompt

from . import __version__
from .shell import ShellToolkit

# Configure logging
logger = logging.getLogger("cliz")

# Configuration constants
CLIZ_HOME_PATH = Path.home() / ".cliz"
CONFIG_FILE_PATH = CLIZ_HOME_PATH / "cliz.yaml"
DB_FILE_PATH = CLIZ_HOME_PATH / "cliz.db"

# Global state
console = Console()
auto_mode = False
response_language = "English"


class ConfigurationError(Exception):
    """Exception raised for configuration file errors."""
    pass


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the cliz configuration from a YAML file.
    
    Args:
        path: Optional path to the configuration file to load
    
    Returns:
        The parsed configuration dictionary
        
    Raises:
        ConfigurationError: If the configuration file cannot be found or read
    """
    # Use specified path if provided
    config_path = Path(path) if path else CONFIG_FILE_PATH
    
    if not config_path.exists():
        raise ConfigurationError(f"No config file found, see https://github.com/xgzlucario/cliz#Install")
    
    # Open the file and pass its contents to yaml.safe_load
    with open(config_path, 'r') as config_file:
        return yaml.safe_load(config_file)
    

def confirm_command_execution(fc: FunctionCall):
    """Request user confirmation before executing a command.
    
    Args:
        fc: The function call to confirm
        
    Raises:
        StopAgentRun: If the user does not confirm the execution
    """
    if auto_mode:
        return
    
    # Pause any live display
    live_display = console._live
    live_display.stop()

    args = fc.arguments
    tool_name = fc.function.name
    full_command = f"{args['command']} {args['args']}"
    
    # Ask for confirmation
    console.print(f"About to run {tool_name}: [bold blue]{full_command}[/]")
    response = (
        Prompt.ask("Do you want to continue?", choices=["y", "n"], default="y")
        .strip()
        .lower()
    )

    # Resume live display
    live_display.start()

    # If the user does not confirm, stop execution
    if response != "y":
        raise StopAgentRun(
            "Command execution cancelled by user",
            agent_message="Execution stopped as permission was not granted.",
        )


@tool
def get_tool_help(command: str, sub_command: Optional[str] = None, help_arg: str = "-h") -> str:
    """Get help information for a command-line tool.

    Args:
        command: The command to get help for
        sub_command: Optional sub-command to get help for
        help_arg: The argument to pass to get help
        
    Returns:
        str: The help text or error message
    """
    return ShellToolkit().help(command, sub_command, help_arg)


@tool(pre_hook=confirm_command_execution)
def run_shell_command(command: str, args: str, work_dir: str = ".") -> str:
    """Run a shell command with the given arguments.

    Args:
        command: The command to execute
        args: Arguments to pass to the command
        work_dir: Working directory for command execution

    Returns:
        str: The command output
    """     
    return ShellToolkit().run(command, args, work_dir)


@tool(pre_hook=confirm_command_execution)
def run_shell_command_background(command: str, args: str, work_dir: str = ".") -> dict:
    """Run a shell command with the given arguments in the background.

    Args:
        command: The command to execute
        args: Arguments to pass to the command
        work_dir: Working directory for command execution

    Returns:
        dict: Process status information
    """
    return ShellToolkit().run_background(command, args, work_dir)


@tool
def fetch_website_content(url: str, output_file: str) -> str:
    """Fetch and save `markdown` formatted content from a website.

    Args:
        url: The URL of the website to fetch
        output_file: The file to save the content to

    Returns:
        A message describing the result of the operation
    """
    try:
        response = httpx.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        # Convert HTML to markdown text
        converter = html2text.HTML2Text()
        converter.ignore_links = True
        text_content = converter.handle(response.text)

        # Save to file
        with open(output_file, "w") as f:
            f.write(text_content)

        return f"Successfully saved content to {output_file} ({len(text_content)} bytes)"
    
    except Exception as e:
        error_msg = f"Failed to fetch content from {url}: {str(e)}"
        logger.error(error_msg)
        return error_msg


SYSTEM_PROMPT = """
你是一个强大的智能命令行助手, 由先进的AI技术驱动。你能够理解和执行各种命令行任务, 帮助用户高效完成工作。

## 主要目标
你的主要目标是直接执行用户的指令，通过命令行工具解决用户的问题。每当用户提出请求时，你应该尽可能地直接解决问题，而不是询问更多细节。

## 工具使用指南
你可以使用以下工具来完成用户任务:

1. get_tool_help - 获取命令行工具的帮助信息
2. run_shell_command - 运行命令行命令
3. run_shell_command_background - 在后台运行命令行命令
4. fetch_website_content - 获取网站内容并保存为markdown格式

遵循这些工具使用规则:
1. 始终使用提供的工具与命令行交互，特别是 get_tool_help、run_shell_command 和 run_shell_command_background。
2. 在使用工具之前, 先评估哪个工具最适合当前任务。
3. 尽量组合使用工具来高效完成任务。
4. 对于需要后台挂起或长时间运行的命令, 优先考虑使用 run_shell_command_background。
5. **永远不要在与用户交流时直接提及工具名称**。例如，不要说 "我将使用 run_shell_command 工具", 而是直接说 "我将运行这个命令"。

## 推理和规划
在执行任务前，你应该：
1. 分析用户的请求，理解其真正的需求
2. 规划最高效的执行路径，考虑可能需要的命令和工具
3. 当面对复杂任务时，将其分解为可管理的步骤
4. 在执行命令前，先考虑该命令的安全性和潜在影响

## 行为规范
1. 直接行动 - 不要问不必要的问题，直接尝试完成任务。
2. 高效执行 - 使用最高效的命令和工具组合完成任务。
3. 清晰沟通 - 简洁明了地解释你的行动和结果。
4. 启发性 - 在适当的时候提供有用的命令行知识和技巧。
5. 主动性 - 预测后续步骤，但在执行前先告知用户。

## 错误处理
1. 当命令执行失败时，分析错误原因并提供解决方案
2. 学习用户的反馈，调整你的方法
3. 在处理敏感操作前提供警告
4. 清晰解释错误情况，避免技术术语过载

## 系统上下文
操作系统: {uname}
工作目录: {work_dir}
当前时间: {datetime}

## 推荐命令行工具
{tools}

用{language}回应。
"""


def main():
    """Main entry point for the cliz application."""
    global auto_mode, response_language
    
    # 1. Parse command line arguments
    parser = argparse.ArgumentParser(
        description="cliz: An intelligent command-line agent"
    )
    parser.add_argument(
        "prompt",
        type=str, 
        help="Task description in natural language"
    )
    parser.add_argument(
        "-a", "--auto", 
        action="store_true",
        help="Run in auto mode without confirmation"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        help="Path to the configuration file"
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Debug mode"
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=__version__,
        help="Show version information"
    )
    args = parser.parse_args()
    
    # 2. Load configuration
    try:
        config = load_config(path=args.config)
        
        # Configure global settings
        response_language = config.get("respond_language", "English")
        auto_mode = config.get("auto", False) or args.auto
        chat_history = config.get("chat_history", False)
           
        # Initialize LLM model
        model_config = config.get("llm")
        if model_config is None:
            raise ConfigurationError("No LLM configuration found, see https://github.com/xgzlucario/cliz#Install")
        
        model = OpenAILike(
            id=model_config.get("model"),
            api_key=model_config.get("api_key"),
            base_url=model_config.get("base_url"),
        )
        
        if auto_mode:
            logger.warning("Running in automatic mode - commands will execute without confirmation")
    
    except (ConfigurationError, KeyError) as e:
        logger.error(f"Configuration error: {e}")
        return 1
    
    # 3. Set up the agent
    system_prompt = SYSTEM_PROMPT.format(
        tools=config.get("tools"),
        uname=platform.uname(),
        work_dir=os.getcwd(),
        datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        language=response_language,
    )
    
    agent = Agent(
        model=model,
        instructions=dedent(system_prompt),
        tools=[
            get_tool_help,
            run_shell_command,
            run_shell_command_background,
            fetch_website_content,
            ThinkingTools()
        ],
        show_tool_calls=True,
        markdown=True,
        debug_mode=args.debug,
        # Chat history configuration
        session_id="fake_session_id",
        storage=SqliteStorage(table_name="agent_sessions", db_file=DB_FILE_PATH),
        add_history_to_messages=chat_history,
        num_history_runs=3,
    )
    
    # 4. Run the agent and print response
    try:
        agent.print_response(
            args.prompt,
            stream=True,
            console=console,
            show_message=False,
            show_intermediate_steps=True,
        )
        return 0
    except Exception as e:
        logger.error(f"Error during agent execution: {e}")
        return 1


if __name__ == "__main__":
    exit(main())