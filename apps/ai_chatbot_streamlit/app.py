import os
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

# Page config
st.set_page_config(
    page_title="Databricks AI Chatbot",
    page_icon="🤖",
    layout="centered"
)

# Initialize Databricks SDK
@st.cache_resource
def get_workspace_client():
    return WorkspaceClient()

w = get_workspace_client()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "custom_context" not in st.session_state:
    st.session_state.custom_context = ""

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Model endpoint configuration
    endpoint_name = st.text_input(
        "Foundation Model Endpoint",
        value=os.environ.get("MODEL_ENDPOINT", "databricks-meta-llama-3-1-70b-instruct"),
        help="Enter the serving endpoint name for your foundation model"
    )
    
    st.divider()
    
    # System prompt
    system_prompt = st.text_area(
        "System Prompt",
        value="You are a helpful AI assistant powered by Databricks.",
        height=100,
        help="Define the behavior and personality of the chatbot"
    )
    
    st.divider()
    
    # Custom context section
    st.subheader("📊 Add Custom Context")
    st.markdown("Add data or information to help the AI answer questions better.")
    
    context_input = st.text_area(
        "Context Data",
        value=st.session_state.custom_context,
        placeholder="Paste data, query results, or any information here...\n\nExample:\n- Product catalog\n- Sales data\n- Company policies\n- Technical documentation",
        height=150,
        help="This context will be included in every message to help the AI provide better answers"
    )
    
    if st.button("💾 Save Context"):
        st.session_state.custom_context = context_input
        st.success("Context saved!")
    
    if st.button("🗑️ Clear Context"):
        st.session_state.custom_context = ""
        st.rerun()
    
    st.divider()
    
    # Model parameters
    st.subheader("🎛️ Model Parameters")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1, 
                           help="Higher = more creative, Lower = more focused")
    max_tokens = st.slider("Max Tokens", 128, 4096, 1024, 128,
                          help="Maximum length of the response")
    
    st.divider()
    
    if st.button("🔄 Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Main content
st.title("🤖 Databricks AI Chatbot")
st.caption(f"Powered by {endpoint_name}")

if st.session_state.custom_context:
    with st.expander("📋 Active Context"):
        st.text(st.session_state.custom_context[:300] + "..." if len(st.session_state.custom_context) > 300 else st.session_state.custom_context)

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask me anything..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Build messages for the API
                messages = []
                
                # Add system prompt with optional context
                full_system_prompt = system_prompt
                if st.session_state.custom_context:
                    full_system_prompt += f"\n\nYou have access to the following context data. Use it to answer questions:\n\n{st.session_state.custom_context}"
                
                messages.append(ChatMessage(role=ChatMessageRole.SYSTEM, content=full_system_prompt))
                
                # Add conversation history
                for msg in st.session_state.messages:
                    role = ChatMessageRole.USER if msg["role"] == "user" else ChatMessageRole.ASSISTANT
                    messages.append(ChatMessage(role=role, content=msg["content"]))
                
                # Call the foundation model endpoint
                response = w.serving_endpoints.query(
                    name=endpoint_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Extract response text
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    assistant_message = response.choices[0].message.content
                else:
                    assistant_message = str(response)
                
                st.markdown(assistant_message)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": assistant_message})
                
            except Exception as e:
                error_message = f"Error: {str(e)}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

# Footer
st.divider()
st.caption("💡 Tip: Add custom context in the sidebar to help the AI answer questions about your specific data or domain.")
