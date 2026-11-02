import { useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import './App.css'

const API_BASE_URL = 'http://localhost:5000'

function formatConversationTitle(conversation) {
  const firstUserMessage = conversation.messages?.find((message) => message.role === 'user')
  if (firstUserMessage?.content) {
    return firstUserMessage.content.trim().slice(0, 28)
  }
  return 'New chat'
}

function generateConversationId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }

  return `conv-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function App() {
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')
  const chatEndRef = useRef(null)

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.conversation_id === activeConversationId) || null,
    [activeConversationId, conversations]
  )
  const isConversationBlocked = activeConversation?.security_status === 'blocked'
  const isSecurityCheckPending = activeConversation?.security_status === 'pending'

  useEffect(() => {
    const loadConversations = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/conversations`)
        const items = response.data || []
        setConversations(items)

        if (items.length > 0) {
          setActiveConversationId(items[0].conversation_id)
          setMessages(items[0].messages || [])
          return
        }

        const newConversationId = generateConversationId()
        const created = await axios.post(`${API_BASE_URL}/conversations`, {
          conversation_id: newConversationId,
        })
        setConversations([created.data])
        setActiveConversationId(created.data.conversation_id)
        setMessages(created.data.messages || [])
      } catch (loadError) {
        console.error('Unable to load conversations:', loadError)
        setError('Unable to load your conversations. Please refresh or try again.')
      }
    }

    loadConversations()
  }, [])

  useEffect(() => {
    if (activeConversation) {
      setMessages(activeConversation.messages || [])
    }
  }, [activeConversation])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

  async function createNewConversation() {
    const conversationId = generateConversationId()
    try {
      const response = await axios.post(`${API_BASE_URL}/conversations`, {
        conversation_id: conversationId,
      })
      const nextConversation = response.data
      setConversations((previous) => [nextConversation, ...previous])
      setActiveConversationId(nextConversation.conversation_id)
      setMessages([])
      setError('')
    } catch (createError) {
      console.error('Unable to create new conversation:', createError)
      setError('Unable to create a new conversation right now.')
    }
  }

  async function handleConversationSelect(conversationId) {
    try {
      const response = await axios.get(`${API_BASE_URL}/conversations/${conversationId}`)
      const loadedConversation = response.data
      setActiveConversationId(conversationId)
      setMessages(loadedConversation.messages || [])
      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.conversation_id === conversationId
            ? { ...conversation, ...loadedConversation }
            : conversation
        )
      )
      setError('')
    } catch (selectError) {
      console.error('Unable to select conversation:', selectError)
      setError('Unable to open that conversation.')
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()

    if (!draft.trim() || isSending || !activeConversationId) {
      return
    }

    const prompt = draft.trim()
    setDraft('')
    setIsSending(true)
    setError('')

    try {
      const response = await axios.post(`${API_BASE_URL}/llm_response`, {
        conversation_id: activeConversationId,
        prompt,
      })

      const assistantMessage = response.data.response || response.data.message || 'No response received.'
      const modelMessage = {
        role: 'user',
        content: prompt,
        timestamp: new Date().toISOString(),
      }
      const assistantReply = {
        role: 'assistant',
        content: assistantMessage,
        timestamp: new Date().toISOString(),
      }

      const updatedMessages = [...messages, modelMessage, assistantReply]
      setMessages(updatedMessages)
      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.conversation_id === activeConversationId
            ? {
                ...conversation,
                messages: updatedMessages,
                security_status: response.data.security_status || conversation.security_status || 'clear',
                updated_at: new Date().toISOString(),
                title: formatConversationTitle({ messages: updatedMessages }),
                preview: assistantMessage,
              }
            : conversation
        )
      )

      if (response.data.security_status === 'blocked') {
        setError('This conversation has been blocked because a prompt injection attempt was detected.')
      }
    } catch (submitError) {
      const message = submitError.response?.data?.message || 'Unable to send your message right now.'
      const securityStatus = submitError.response?.data?.security_status
      if (securityStatus === 'blocked' || securityStatus === 'pending') {
        setConversations((previous) =>
          previous.map((conversation) =>
            conversation.conversation_id === activeConversationId
              ? { ...conversation, security_status: securityStatus }
              : conversation
          )
        )
      }
      if (securityStatus === 'pending') {
        setDraft(prompt)
      }
      setError(message)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="chat-app-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div>
            <span className="eyebrow">PromptGuard</span>
            <h1>Chats</h1>
          </div>
          <button className="new-chat-button" type="button" onClick={createNewConversation}>
            New chat
          </button>
        </div>

        <div className="conversation-list">
          {conversations.map((conversation) => (
            <button
              key={conversation.conversation_id}
              type="button"
              className={`conversation-item ${conversation.conversation_id === activeConversationId ? 'is-active' : ''}`}
              onClick={() => handleConversationSelect(conversation.conversation_id)}
            >
              <span className="conversation-item__title">
                {formatConversationTitle(conversation)}
              </span>
              <span className="conversation-item__preview">{conversation.preview || 'No messages yet'}</span>
              <span className={`conversation-item__status ${conversation.security_status || 'clear'}`}>
                {conversation.security_status || 'clear'}
              </span>
            </button>
          ))}
        </div>
      </aside>

      <main className="chat-panel">
        <header className="chat-header">
          <div>
            <span className="eyebrow">Conversation</span>
            <h2>{activeConversation ? formatConversationTitle(activeConversation) : 'New chat'}</h2>
          </div>
          <span className={`status-pill ${activeConversation?.security_status || 'clear'}`}>
            {activeConversation?.security_status || 'clear'}
          </span>
        </header>

        <section className="message-list" aria-live="polite">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>Start a protected conversation.</p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={`${message.role}-${message.timestamp || index}`}
                className={`message-row ${message.role === 'user' ? 'message-row--user' : 'message-row--assistant'}`}
              >
                <div className={`message-bubble ${message.role === 'user' ? 'message-bubble--user' : 'message-bubble--assistant'}`}>
                  {message.content}
                </div>
              </div>
            ))
          )}

          {isSending && (
            <div className="message-row message-row--assistant">
              <div className="message-bubble message-bubble--assistant typing-indicator" aria-label="Waiting for assistant response">
                <span /> <span /> <span />
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </section>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            aria-label="Message input"
            rows="1"
            value={draft}
            placeholder={
              isConversationBlocked
                ? 'This conversation is blocked. Start a new chat to continue.'
                : isSecurityCheckPending
                  ? 'Security check pending. Retry your message to check the status.'
                  : 'Ask PromptGuard anything...'
            }
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                handleSubmit(event)
              }
            }}
            disabled={isSending || !activeConversationId || isConversationBlocked}
          />
          <button
            type="submit"
            disabled={
              isSending ||
              !draft.trim() ||
              !activeConversationId ||
              isConversationBlocked
            }
          >
            {isSending ? 'Sending…' : 'Send'}
          </button>
        </form>

        {isConversationBlocked ? (
          <div className="error-banner" role="status">
            This conversation is blocked. Start a new chat to continue.
          </div>
        ) : isSecurityCheckPending ? (
          <div className="error-banner" role="status">
            Security status is unresolved. Retrying your message will recheck it; no prompt is forwarded unless it is clear.
          </div>
        ) : error ? (
          <div className="error-banner" role="alert">{error}</div>
        ) : null}
      </main>
    </div>
  )
}

export default App
