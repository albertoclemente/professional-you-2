from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr
import tempfile


load_dotenv(override=True)


def text_to_speech(text):
    """Convert text to speech using ElevenLabs API and return audio file path"""
    # Get credentials at runtime (important for HuggingFace Spaces)
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
    elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    
    print(f"DEBUG: Attempting TTS - API Key: {'set' if elevenlabs_api_key else 'MISSING'}, Voice ID: {'set' if elevenlabs_voice_id else 'MISSING'}")
    
    if not elevenlabs_api_key or not elevenlabs_voice_id:
        print(f"ElevenLabs not configured - API Key: {'set' if elevenlabs_api_key else 'missing'}, Voice ID: {'set' if elevenlabs_voice_id else 'missing'}")
        return None
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": elevenlabs_api_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    try:
        print(f"DEBUG: Calling ElevenLabs API...")
        response = requests.post(url, json=data, headers=headers)
        print(f"DEBUG: Response status: {response.status_code}")
        
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                f.write(response.content)
                print(f"DEBUG: Audio saved to {f.name}")
                return f.name
        else:
            print(f"ElevenLabs API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error generating speech: {e}")
        return None

def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    push(f"Recording {question}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]


class Me:

    def __init__(self):
        self.openai = OpenAI()
        self.name = "Alberto Clemente"
        reader = PdfReader("me/Profile.pdf")
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open("me/summary.txt", "r", encoding="utf-8") as f:
            self.summary = f.read()


    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results
    
    def system_prompt(self):
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt
    
    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        response = None
        while not done:
            response = self.openai.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools, max_tokens=300)
            if response.choices[0].finish_reason=="tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content if response else ""
    
    def chat_stream(self, message, history):
        """Generator function that yields text chunks for streaming effect"""
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        
        # First, handle any tool calls (non-streaming)
        done = False
        while not done:
            response = self.openai.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools, max_tokens=300)
            finish_reason = response.choices[0].finish_reason
            
            if finish_reason == "tool_calls":
                msg = response.choices[0].message
                tool_calls = msg.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(msg)
                messages.extend(results)
            else:
                done = True
        
        # Now stream the final response
        full_response = ""
        stream = self.openai.chat.completions.create(
            model="gpt-4o-mini", 
            messages=messages, 
            stream=True,
            max_tokens=300
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
                yield full_response
        
        return full_response
    

if __name__ == "__main__":
    me = Me()
    
    # Custom CSS for better styling
    custom_css = """
    .gradio-container {
        max-width: 1200px !important;
        margin: auto !important;
    }
    .header-container {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #2c5364 0%, #203a43 50%, #0f2027 100%);
        border-radius: 15px;
        margin-bottom: 20px;
        color: white;
    }
    .header-title {
        font-size: 2.5em;
        margin-bottom: 10px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    .header-subtitle {
        font-size: 1.2em;
        opacity: 0.9;
    }
    .info-text {
        color: #4a5568;
        font-size: 0.95em;
        line-height: 1.6;
    }
    .info-text h3 {
        color: #2d3748;
        margin-bottom: 8px;
    }
    .info-text ul {
        margin: 0;
        padding-left: 20px;
    }
    .example-btn {
        margin: 5px !important;
        border-radius: 20px !important;
    }
    .chat-container {
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background-color: #48bb78;
        margin-right: 8px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    footer {
        text-align: center;
        padding: 20px;
        color: #666;
        font-size: 0.9em;
    }
    """
    
    def respond_stream(message, chat_history):
        """Stream the response character by character"""
        if not message.strip():
            yield "", chat_history, None
            return
            
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": ""})
        
        for partial_response in me.chat_stream(message, chat_history[:-2]):
            chat_history[-1]["content"] = partial_response
            yield "", chat_history, None
        
        # After streaming is complete, generate audio
        audio_path = text_to_speech(chat_history[-1]["content"])
        yield "", chat_history, audio_path
    
    def clear_chat():
        return [], None
    
    def generate_voice_click(chat_history):
        if chat_history and len(chat_history) > 0:
            last_message = chat_history[-1]
            if last_message.get("role") == "assistant":
                return text_to_speech(last_message["content"])
        return None
    
    def use_example(example_text, chat_history):
        """Handle example button clicks"""
        return example_text
    
    with gr.Blocks(css=custom_css, theme=gr.themes.Soft(
        primary_hue="teal",
        secondary_hue="cyan",
        neutral_hue="gray"
    )) as demo:
        
        # Header Section
        gr.HTML("""
        <div class="header-container">
            <div class="header-title">🤖 Professional You 2.0</div>
            <div class="header-subtitle">Talk to My AI Clone • Powered by GPT-4 & ElevenLabs Voice Cloning</div>
        </div>
        """)
        
        with gr.Row():
            # Left Sidebar - Info Panel (clean text, no cards)
            with gr.Column(scale=1):
                gr.Markdown("""
### 👋 About Me

Hi! I'm **Alberto Clemente**'s AI clone. I can tell you about his professional background, skills, experience, and career journey.

---

### 💡 What I Can Help With

- Professional background
- Technical skills & expertise  
- Work experience
- Career highlights
- Contact & scheduling

---

### 🎤 Voice Feature

Click the voice button to hear responses in Alberto's cloned voice!

---

### 📊 Status

🟢 AI Clone Online  
🟢 Voice Enabled
                """)
            
            # Main Chat Area
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    type="messages", 
                    height=450,
                    label="💬 Chat",
                    avatar_images=(None, "https://api.dicebear.com/7.x/bottts/svg?seed=alberto"),
                    elem_classes=["chat-container"]
                )
                
                # Example Questions
                gr.Markdown("### 🚀 Quick Questions")
                with gr.Row():
                    example1 = gr.Button("What's your background?", size="sm", variant="secondary")
                    example2 = gr.Button("Tell me about your skills", size="sm", variant="secondary")
                    example3 = gr.Button("What are you working on?", size="sm", variant="secondary")
                with gr.Row():
                    example4 = gr.Button("How can I contact you?", size="sm", variant="secondary")
                    example5 = gr.Button("What makes you unique?", size="sm", variant="secondary")
                    example6 = gr.Button("Career highlights?", size="sm", variant="secondary")
                
                # Input Area
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="💭 Ask me anything about Alberto's professional journey...",
                        label="",
                        scale=4,
                        container=False
                    )
                    submit_btn = gr.Button("Send 📤", variant="primary", scale=1)
                
                # Audio Output
                with gr.Row():
                    audio_output = gr.Audio(
                        label="🎙️ Voice Response",
                        autoplay=True,
                        elem_classes=["audio-container"]
                    )
                
                # Action Buttons
                with gr.Row():
                    generate_voice = gr.Button("🔊 Replay Voice", variant="secondary")
                    clear = gr.Button("🗑️ Clear Chat", variant="stop")
        
        # Footer
        gr.HTML("""
        <footer>
            <p>Built with ❤️ using OpenAI GPT-4o-mini & ElevenLabs Voice Cloning</p>
            <p>© 2024 Alberto Clemente • <a href="https://github.com/albertoclemente" target="_blank">GitHub</a></p>
        </footer>
        """)
        
        # Event handlers
        msg.submit(respond_stream, [msg, chatbot], [msg, chatbot, audio_output])
        submit_btn.click(respond_stream, [msg, chatbot], [msg, chatbot, audio_output])
        clear.click(clear_chat, outputs=[chatbot, audio_output])
        generate_voice.click(generate_voice_click, inputs=[chatbot], outputs=[audio_output])
        
        # Example button handlers
        example1.click(lambda: "What's your professional background?", outputs=[msg])
        example2.click(lambda: "Tell me about your technical skills and expertise", outputs=[msg])
        example3.click(lambda: "What projects are you currently working on?", outputs=[msg])
        example4.click(lambda: "How can I get in touch with you?", outputs=[msg])
        example5.click(lambda: "What makes you unique as a professional?", outputs=[msg])
        example6.click(lambda: "What are your career highlights?", outputs=[msg])
    
    demo.launch()
    