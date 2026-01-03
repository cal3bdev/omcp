"""
Gradio Web UI for MCP Agent.

Interactive chat interface for testing MCP tools.
"""

import asyncio
import os
from dotenv import load_dotenv

import gradio as gr
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai import types

load_dotenv()

# Global state
_toolset: McpToolset | None = None
_agent: LlmAgent | None = None
_runner: InMemoryRunner | None = None
_session_id: str | None = None


async def initialize_agent(mcp_url: str):
    """Initialize the agent with the given MCP URL."""
    global _toolset, _agent, _runner, _session_id
    
    # Close existing toolset if any
    if _toolset:
        await _toolset.close()
    
    _toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=mcp_url),
    )
    
    _agent = LlmAgent(
        model="gemini-2.0-flash",
        name="mcp_chat_agent",
        instruction="""You are a helpful assistant with access to various API tools.
Use the available tools to help answer user queries.
Be concise but thorough in your responses.
When you use a tool, briefly explain what you're doing.""",
        tools=[_toolset],
    )
    
    _runner = InMemoryRunner(agent=_agent, app_name="mcp_web_client")
    
    # Create session
    session = await _runner.session_service.create_session(
        app_name="mcp_web_client",
        user_id="web_user",
    )
    _session_id = session.id
    
    # Get tool count
    tools = await _toolset.get_tools()
    return len(tools)


async def get_available_tools(mcp_url: str) -> str:
    """Get list of available tools from MCP server."""
    try:
        toolset = McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=mcp_url),
        )
        tools = await toolset.get_tools()
        await toolset.close()
        
        tool_list = "\n".join([f"• **{t.name}**: {t.description[:100]}..." 
                               if len(t.description) > 100 else f"• **{t.name}**: {t.description}"
                               for t in tools[:50]])
        
        if len(tools) > 50:
            tool_list += f"\n\n... and {len(tools) - 50} more tools"
        
        return f"**Available Tools ({len(tools)} total):**\n\n{tool_list}"
    except Exception as e:
        return f"❌ Error fetching tools: {e}"


async def chat(message: str, history: list, mcp_url: str) -> tuple[str, list]:
    """Process a chat message."""
    global _runner, _session_id, _toolset
    
    if not _runner or not _session_id:
        try:
            tool_count = await initialize_agent(mcp_url)
            yield f"✓ Connected to MCP server ({tool_count} tools available)\n\n", history
        except Exception as e:
            yield f"❌ Failed to connect: {e}", history
            return
    
    response_text = ""
    tool_calls = []
    
    try:
        async for event in _runner.run_async(
            user_id="web_user",
            session_id=_session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=message)]
            ),
        ):
            if hasattr(event, 'content') and event.content and event.content.parts:
                for part in event.content.parts:
                    # Handle text responses
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
                        yield response_text, history
                    
                    # Handle function calls
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        tool_calls.append(f"🔧 `{fc.name}`")
        
        # Add tool call info to response
        if tool_calls:
            tool_info = "\n\n---\n*Tools used: " + ", ".join(tool_calls) + "*"
            response_text += tool_info
            yield response_text, history
            
    except Exception as e:
        response_text = f"❌ Error: {e}"
        yield response_text, history


def reset_session():
    """Reset the chat session."""
    global _toolset, _agent, _runner, _session_id
    
    if _toolset:
        asyncio.get_event_loop().run_until_complete(_toolset.close())
    
    _toolset = None
    _agent = None
    _runner = None
    _session_id = None
    
    return [], "Session reset. Enter a message to reconnect."


def create_ui():
    """Create the Gradio interface."""
    
    with gr.Blocks(title="MCP Agent Chat") as demo:
        gr.Markdown("""
        # 🤖 MCP Agent Chat
        
        Chat with an AI agent that has access to MCP server tools.
        """)
        
        with gr.Row():
            with gr.Column(scale=3):
                mcp_url = gr.Textbox(
                    label="MCP Server URL",
                    value=os.getenv("MCP_URL", "http://localhost:9000/mcp"),
                    placeholder="http://localhost:9000/mcp",
                )
            with gr.Column(scale=1):
                connect_btn = gr.Button("🔍 List Tools", variant="secondary")
        
        tools_display = gr.Markdown(visible=False)
        
        chatbot = gr.Chatbot(
            label="Chat",
            height=400,
        )
        
        with gr.Row():
            msg = gr.Textbox(
                label="Message",
                placeholder="Type your message here...",
                scale=4,
                show_label=False,
            )
            submit_btn = gr.Button("Send", variant="primary", scale=1)
        
        with gr.Row():
            clear_btn = gr.Button("🗑️ Clear Chat")
            reset_btn = gr.Button("🔄 Reset Session")
        
        # Example prompts
        gr.Markdown("### 💡 Example Prompts")
        with gr.Row():
            ex1 = gr.Button("List all products", size="sm")
            ex2 = gr.Button("Get user profile for user 123", size="sm")
            ex3 = gr.Button("Check system health", size="sm")
        
        status = gr.Markdown("")
        
        # Event handlers
        async def show_tools(url):
            tools = await get_available_tools(url)
            return gr.update(value=tools, visible=True)
        
        connect_btn.click(
            fn=show_tools,
            inputs=[mcp_url],
            outputs=[tools_display],
        )
        
        async def respond(message, chat_history, url):
            if not message.strip():
                return "", chat_history

            chat_history = chat_history + [(message, None)]

            response = ""
            async for text, _ in chat(message, chat_history, url):
                response = text

            chat_history[-1] = (message, response)
            return "", chat_history
        
        msg.submit(
            fn=respond,
            inputs=[msg, chatbot, mcp_url],
            outputs=[msg, chatbot],
        )
        
        submit_btn.click(
            fn=respond,
            inputs=[msg, chatbot, mcp_url],
            outputs=[msg, chatbot],
        )
        
        clear_btn.click(lambda: [], outputs=[chatbot])
        reset_btn.click(fn=reset_session, outputs=[chatbot, status])
        
        # Example button handlers
        ex1.click(lambda: "List all available products", outputs=[msg])
        ex2.click(lambda: "Get the profile information for user with ID 123", outputs=[msg])
        ex3.click(lambda: "Check the system health status", outputs=[msg])
        
    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(),
    )
