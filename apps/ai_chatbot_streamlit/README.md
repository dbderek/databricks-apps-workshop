# AI Chatbot with Databricks Foundation Models

A simple Streamlit chatbot that demonstrates how to build conversational AI using Databricks Foundation Model APIs.

## Features

- 🤖 **Configurable Foundation Models**: Switch between different Databricks FM endpoints from the UI
- 💬 **Interactive Chat Interface**: Clean chat UI with message history
- 📊 **Custom Context**: Paste any data or information to help the AI answer domain-specific questions
- 🎛️ **Adjustable Parameters**: Control temperature and max tokens in real-time
- ⚙️ **System Prompts**: Customize the chatbot's behavior and personality

## How It Works

1. **Choose a Model**: Configure which Databricks Foundation Model endpoint to use
2. **Add Context** (Optional): Paste data like product catalogs, sales figures, or documentation that the AI should reference
3. **Chat**: Ask questions and the AI will respond using the model and any context you've provided

## Configuration

The app can be configured via environment variables in `app.yml`:

- `MODEL_ENDPOINT`: The Databricks serving endpoint name (default: `databricks-meta-llama-3-1-70b-instruct`)

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Databricks credentials (if testing locally)
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=your-token

# Run the app
streamlit run app.py
```

## Deploying to Databricks Apps

1. Ensure you have a Foundation Model serving endpoint available
2. Update the `MODEL_ENDPOINT` in `app.yml` if using a different endpoint
3. Deploy using Databricks Apps
4. The app will automatically authenticate using the app service principal

## Usage Example

**Scenario**: You want to build a chatbot that can answer questions about your product catalog.

1. **Add Context**: Copy your product data into the "Custom Context" field:
   ```
   Products:
   - Widget A: $10, in stock, electronics category
   - Widget B: $25, out of stock, home goods category
   - Widget C: $15, in stock, electronics category
   ```

2. **Save the Context**: Click "Save Context"

3. **Ask Questions**: 
   - "What electronics do you have in stock?"
   - "How much does Widget B cost?"
   - "Show me all products under $20"

The AI will use your context data to provide accurate answers!

## Workshop Notes

This app demonstrates:
- Integration with Databricks Foundation Model APIs via the SDK
- Stateful conversation management with Streamlit session state
- Dynamic configuration from the UI
- Context injection for domain-specific knowledge
- Best practices for Streamlit + Databricks integration
