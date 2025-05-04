import argparse
import logging
import os
import platform
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional

import html2text
import httpx
import yaml
from agno.agent import Agent
from agno.exceptions import StopAgentRun
from agno.models.openai.like import OpenAILike
from agno.storage.sqlite import SqliteStorage
from agno.tools import FunctionCall, tool
from rich.console import Console
from rich.pretty import pprint
from rich.prompt import Prompt

from . import __version__
from .model import CommandLineTool

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
    full_command = f"{args['command']} {args['args']}"
    
    # Ask for confirmation
    console.print(f"About to run: [bold blue]{full_command}[/]")
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
    tool = CommandLineTool(name=command)
    
    print(command, sub_command, help_arg)
    
    return tool.help(sub_command=sub_command, help_arg=help_arg)


@tool(pre_hook=confirm_command_execution)
def execute_command(command: str, args: str, work_dir: str = ".") -> str:
    """Execute a command-line tool with the given arguments.

    Args:
        command: The command to execute
        args: Arguments to pass to the command
        work_dir: Working directory for command execution

    Returns:
        str: The command output
    """
    tool = CommandLineTool(name=command)
    
    print(command, args, work_dir)
        
    return tool.execute(args=args, work_dir=work_dir)


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


@tool
def think(thought: str) -> str:
    """Process a thought without executing any external commands.

    This tool allows the agent to process complex reasoning or store
    intermediate calculations without performing any side effects.

    Args:
        thought: The thought to process

    Returns:
        The thought, unchanged
    """
    return thought


# System prompt template for the agent
SYSTEM_PROMPT = """
You are a helpful assistant that uses command-line tools to complete the user's tasks.
Follow these instructions strictly:

1. You can use the provided tools or other system tools as appropriate.
2. Always use `get_tool_help` and `execute_command` to interact with command-line tools.
3. Use the appropriate tool combinations to complete the task efficiently.
4. Do not ask unnecessary questions - try to accomplish the task directly.

System Context:
OS: {os}-{arch}
WorkDir: {work_dir}
Datetime: {datetime}

Preffered command-line tools:
{tools}

Respond in {language}.
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
        os=platform.system(),
        arch=platform.machine(),
        work_dir=os.getcwd(),
        datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        language=response_language,
    )
    
    agent = Agent(
        model=model,
        instructions=dedent(system_prompt),
        tools=[get_tool_help, execute_command, fetch_website_content, think],
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