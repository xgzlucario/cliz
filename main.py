import argparse
import os
from textwrap import dedent
from typing import Optional

import html2text
import requests
import yaml
from agno.agent import Agent
from agno.exceptions import StopAgentRun
from agno.models.openai.like import OpenAILike
from agno.tools import FunctionCall, tool
from rich.console import Console
from rich.prompt import Prompt

from model import Result, Tool

CONFIG_FILE = "cliq.yaml"
CONFIG_DIR = os.path.expanduser("~/.cliq")

yolo_mode = False
respond_language = "English"
global_tools = []

console = Console()

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f)
        
    elif os.path.exists(f"{CONFIG_DIR}/{CONFIG_FILE}"):
        with open(f"{CONFIG_DIR}/{CONFIG_FILE}", "r") as f:
            return yaml.safe_load(f)
        
    else:
        raise FileNotFoundError(f"cliq.yaml not found in {CONFIG_DIR}")

def pre_hook(fc: FunctionCall):
    if yolo_mode:
        return
    
    live = console._live
    live.stop()

    args = fc.arguments
    full_command = f"{args['command']} {args['args']}"
    
    # Ask for confirmation
    console.print(f"About to run: [bold blue]{full_command}[/]")
    message = (
        Prompt.ask("Do you want to continue?", choices=["y", "n"], default="y")
        .strip()
        .lower()
    )

    live.start()

    # If the user does not want to continue, raise a StopExecution exception
    if message != "y":
        raise StopAgentRun(
            "Tool call cancelled by user",
            agent_message="Stopping execution as permission was not granted.",
        )

def tool_help(command: str, sub_command: Optional[str] = None) -> Result:
    """Use this function to get cli tool help.

    Args:
        command (str): The command to get help for.
        sub_command (str, optional): The sub-command to get help for. Defaults to None.

    Returns:
        str: text of help.
    """
    
    tool = next((t for t in global_tools if t.name == command), None)
    if tool is None:
        return Result(success=False, stderr=f"tool {command} not found")
    
    return tool.help(sub_command=sub_command)

@tool(pre_hook=pre_hook)
def tool_execute(command: str, args: str, work_dir: str = ".") -> Result:
    """Use this function to execute cli tool.

    Args:
        command (str): The command to execute.
        args (str): The arguments to pass to the command.
        work_dir (str, optional): The working directory. Defaults to ".".

    Returns:
        Result: result of tool execution.
    """
        
    tool = Tool(name=command)
    return tool.execute(args=args, work_dir=work_dir)

def fetch_website_content(url: str, output_file: str) -> str:  
    """Use this function to fetch static website page content.

    Args:
        url (str): The URL of the website to fetch.
        output_file (str): The file to save the content to.

    Returns:
        str: message of execution result.
    """
    
    text = requests.get(url).text
    h = html2text.HTML2Text()
    h.ignore_links = True
    text = h.handle(text)

    with open(output_file, "w") as f:
        f.write(text)

    return f"Saved content to {output_file} with size {len(text)}."

def think(thought: str) -> str:
    """Use the tool to think about something. It will not obtain new information or change the database, but just append the thought to the log. Use it when complex reasoning or some cache memory is needed.

    Args:
        thought (str): The thought to think about.

    Returns:
        str: message of execution result.
    """
    
    return thought

SYSTEM_PROMPT = """
You are a helpful assistant that use cli tools to complete the user's task. Follow the instructions strictly:
1. You can use the tools preferred or the other system tools is OK.
2. MUST USE `tool_help` and `tool_execute` to execute the command-line tool.
3. Use the appropriate tool combination to complete the task, don't ask any questions.

Current working directory:
{work_dir}

Preferred command-line tools:
{tools}

Respond in {language}.
"""

if __name__ == "__main__":
    config = load_config()
    
    # 1. Load config
    respond_language = config["respond_language"]
    yolo_mode = config["yolo"]
    global_tools = [Tool(**tool) for tool in config["tools"]]
    
    # 2. Parse arguments
    parser = argparse.ArgumentParser(description="cliq: A useful command-line agent help you work with your favorite tools!")
    parser.add_argument('prompt', type=str, help='The prompt to send to the agent.')
    parser.add_argument('--yolo', action='store_true', help='enable YOLO (you only live once) mode.')
    args = parser.parse_args()
    
    if yolo_mode or args.yolo:
        yolo_mode = True
        logger.warning("you are now in YOLO mode")

    model = OpenAILike(
        id=config["llm"]["model"],
        api_key=config["llm"]["api_key"],
        base_url=config["llm"]["base_url"],
    )

    prompt = SYSTEM_PROMPT.format(
        tools=[tool.__dict__() for tool in global_tools],
        work_dir=os.getcwd(),
        language=respond_language,
    )
  
    agent = Agent(
        model=model,
        instructions=dedent(prompt),
        tools=[tool_help, tool_execute, fetch_website_content, think],
        show_tool_calls=True,
        markdown=True,
    )

    # 3. Run agent
    agent.print_response(
        args.prompt,
        stream=True,
        console=console,
    )