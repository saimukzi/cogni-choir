# User requirement

## Software
- There is NO user managment in the software.  Suppose there is only one user.
- UI language:
  - Traditional Chinese
  - English
  - May support more later
- The software should be able to run on Windows

## Chatroom
- The software contains multiple chatrooms.
- User can manage the chatroom.
  - Delete chatroom
  - Rename chatroom
  - Clone chatroom
- It can be multiple AI bot in a chatroom.
- Each AI bot act as a role.
- It is possible that multiple roles are backed by the same AI engine.
- User can manage the AIs ANYTIME
  - User can add AI to the chatroom and assign a role and system prompt.
  - User can remove AI from the chatroom.
  - All AI role add/removal will be seen by other AI bots.
  - User can change the AI engine (ChatGPT/Grok/Gemini) and AI engine version of a role.
  - User can edit the system prompt
- User can leave message in the chatroom.
- User can select one of the AI bot in the room to leave the next message.
- All message history will be stored in the chatroom.
- User can manage message history
  - Delete chat message
  - Create fake chat history

# Third party AIs
- The software support different AI API providers
  - Google Gemini
  - xAI Grok
  - OpenAI ChatGPT
  - etc.
- User need to provide API keys
- The software call the API servers directly
- The software store the API keys
