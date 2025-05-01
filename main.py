import argparse
import logging
import os
from pathlib import Path
from textwrap import dedent
from typing import Dict, List, Optional, Any

import html2text
import requests
import yaml
from agno.agent import Agent
from agno.exceptions import StopAgentRun
from agno.models.openai.like import OpenAILike
from agno.tools import FunctionCall, tool
from rich.console import Console
from rich.prompt import Prompt

from model import CommandLineTool, CommandResult

# Configure logging
logger = logging.getLogger("cliq")

# Configuration constants
CONFIG_FILENAME = "cliq.yaml"
CONFIG_DIR = Path.home() / ".cliq"
DEFAULT_CONFIG_PATH = CONFIG_DIR / CONFIG_FILENAME
LOCAL_CONFIG_PATH = Path(CONFIG_FILENAME)

# Global state
console = Console()
available_tools: List[CommandLineTool] = []
auto_mode = False
response_language = "English"


class ConfigurationError(Exception):
    """Exception raised for configuration file errors."""
    pass


def load_config() -> Dict[str, Any]:
    """Load the CLIQ configuration from a YAML file.
    
    Returns:
        The parsed configuration dictionary
        
    Raises:
        ConfigurationError: If the configuration file cannot be found or read
    """
    config_paths = [LOCAL_CONFIG_PATH, DEFAULT_CONFIG_PATH]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    return yaml.safe_load(f)
            except Exception as e:
                raise ConfigurationError(f"Error reading config from {config_path}: {e}")
    
    # If we get here, no config file was found
    raise ConfigurationError(
        f"Configuration file not found. Looked in: {', '.join(str(p) for p in config_paths)}"
    )


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
def get_tool_help(command: str, sub_command: Optional[str] = None) -> CommandResult:
    """Get help information for a command-line tool.

    Args:
        command: The command to get help for
        sub_command: Optional sub-command to get help for

    Returns:
        CommandResult containing the help text or error message
    """
    matching_tool = next((t for t in available_tools if t.name == command), None)
    if matching_tool is None:
        return CommandResult(success=False, stderr=f"Tool '{command}' not found")
    
    return matching_tool.help(sub_command=sub_command)


@tool(pre_hook=confirm_command_execution)
def execute_command(command: str, args: str, work_dir: str = ".") -> CommandResult:
    """Execute a command-line tool with the given arguments.

    Args:
        command: The command to execute
        args: Arguments to pass to the command
        work_dir: Working directory for command execution

    Returns:
        CommandResult containing the command output and execution status
    """
    tool = CommandLineTool(name=command)
        
    return tool.execute(args=args, work_dir=work_dir)


@tool
def fetch_website_content(url: str, output_file: str) -> str:
    """Fetch and save content from a website.

    Args:
        url: The URL of the website to fetch
        output_file: The file to save the content to

    Returns:
        A message describing the result of the operation
    """
    try:
        response = requests.get(url)
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

Current working directory:
{work_dir}

Available command-line tools:
{tools}

Respond in {language}.
"""


def main():
    """Main entry point for the CLIQ application."""
    global available_tools, auto_mode, response_language
    
    # 1. Parse command line arguments
    parser = argparse.ArgumentParser(
        description="CLIQ: An intelligent command-line agent"
    )
    parser.add_argument(
        "prompt", 
        type=str, 
        help="Natural language request to send to the assistant"
    )
    parser.add_argument(
        "-a", "--auto", 
        action="store_true", 
        help="Run in automatic mode without confirmation prompts"
    )
    args = parser.parse_args()
    
    # 2. Load configuration
    try:
        config = load_config()
        
        # Configure global settings
        response_language = config.get("respond_language", "English")
        auto_mode = config.get("auto", False) or args.auto
        
        # Initialize tools from configuration
        available_tools = [CommandLineTool(**tool_config) for tool_config in config.get("tools", [])]
        
        # Initialize LLM model
        model_config = config.get("llm", {})
        model = OpenAILike(
            id=model_config.get("model", ""),
            api_key=model_config.get("api_key", ""),
            base_url=model_config.get("base_url", ""),
        )
        
        if auto_mode:
            logger.warning("Running in automatic mode - commands will execute without confirmation")
    
    except (ConfigurationError, KeyError) as e:
        logger.error(f"Configuration error: {e}")
        return 1
    
    # 3. Set up the agent
    system_prompt = SYSTEM_PROMPT.format(
        tools=[tool.to_dict() for tool in available_tools],
        work_dir=os.getcwd(),
        language=response_language,
    )
    
    print(system_prompt)
    
    agent = Agent(
        model=model,
        instructions=dedent(system_prompt),
        tools=[get_tool_help, execute_command, fetch_website_content, think],
        show_tool_calls=True,
        markdown=True,
    )
    
    # 4. Run the agent and print response
    try:
        agent.print_response(
            args.prompt,
            stream=True,
            console=console,
        )
        return 0
    except Exception as e:
        logger.error(f"Error during agent execution: {e}")
        return 1


if __name__ == "__main__":
    exit(main())