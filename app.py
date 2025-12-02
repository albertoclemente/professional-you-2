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
            response = self.openai.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)
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
            response = self.openai.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)
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
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
                yield full_response
        
        return full_response
    

if __name__ == "__main__":
    me = Me()
    
    def respond_stream(message, chat_history):
        """Stream the response character by character"""
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
    
    with gr.Blocks() as demo:
        gr.Markdown("# Professional You 2.0 - Talk to My AI Clone 🤖🎙️")
        
        chatbot = gr.Chatbot(type="messages", height=400)
        audio_output = gr.Audio(label="🔊 Voice Response (Your Cloned Voice)", autoplay=True)
        msg = gr.Textbox(placeholder="Type your message here...", label="Your Message")
        
        with gr.Row():
            clear = gr.Button("Clear Chat")
            generate_voice = gr.Button("🔊 Generate Voice for Last Response")
        
        msg.submit(respond_stream, [msg, chatbot], [msg, chatbot, audio_output])
        clear.click(clear_chat, outputs=[chatbot, audio_output])
        generate_voice.click(generate_voice_click, inputs=[chatbot], outputs=[audio_output])
    
    demo.launch()
    