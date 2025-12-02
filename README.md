# Professional You 2.0 - AI Career Chatbot 🤖🎙️

An AI-powered career chatbot that lets you talk to my AI clone! Built with OpenAI GPT-4o-mini and ElevenLabs voice cloning.

## Features

- 💬 **Interactive Chat**: Ask questions about my professional background, skills, and experience
- 🎤 **Voice Output**: Hear responses in my cloned voice using ElevenLabs TTS
- 📄 **RAG-powered**: Uses my resume and LinkedIn data for accurate responses
- 🔧 **Tool Calling**: Integrated with custom tools for scheduling meetings and sending notifications
- 🌐 **Web Deployment**: Deployed on HuggingFace Spaces with Gradio

## Live Demo

🚀 [Try it on HuggingFace Spaces](https://huggingface.co/spaces/albyos/Spaces_professional_you_2.0)

## Tech Stack

- **LLM**: OpenAI GPT-4o-mini
- **Voice**: ElevenLabs Text-to-Speech with custom voice cloning
- **Framework**: Gradio
- **Vector Store**: ChromaDB for RAG
- **Deployment**: HuggingFace Spaces

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your API keys:
   ```
   OPENAI_API_KEY=your_openai_key
   ELEVENLABS_API_KEY=your_elevenlabs_key
   ELEVENLABS_VOICE_ID=your_voice_id
   PUSHOVER_USER=your_pushover_user (optional)
   PUSHOVER_TOKEN=your_pushover_token (optional)
   ```
4. Add your resume/profile data in the `me/` folder
5. Run the app:
   ```bash
   python app.py
   ```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `ELEVENLABS_API_KEY` | Your ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | Your cloned voice ID from ElevenLabs |
| `PUSHOVER_USER` | (Optional) Pushover user key for notifications |
| `PUSHOVER_TOKEN` | (Optional) Pushover app token for notifications |

## Credits

Based on the [Agentic AI course](https://github.com/ed-donner/agents) by Ed Donner.

## Author

**Alberto Clemente**

## License

MIT
