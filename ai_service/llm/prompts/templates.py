from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

def get_chat_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", "You are a helpful and concise AI assistant."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
