# Interactive Chat

## Overview
Users can ask natural language questions about the uploaded document, and the AI will respond based specifically on that document's content.

## Key Features
- **Context-Aware**: Answers are grounded strictly in the document text.
- **Conversation History**: The AI remembers previous turns, allowing for follow-up questions. History is persisted locally via SQLite.
- **Premium UI**: Glassmorphism aesthetic, continuous background animations, and smooth transitions.
- **Real-time Feedback**:
    - **Typing Indicators**: Bouncing dots appear while the AI is thinking.
    - **Toast Notifications**: Non-intrusive popups for errors or success messages.

## Usage
Simply type a question in the input box and press Enter. The system will display a "Typing..." indicator while it retrieves relevant sections and generates an answer. Responses are saved automatically.
