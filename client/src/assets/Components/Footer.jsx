import axios from 'axios'
import React, { useState } from 'react'

function Footer({ setMessages }) {
  const handlePromptInput = (event) => {
    const promptInput = event.currentTarget
    promptInput.style.height = 'auto'
    promptInput.style.height = `${promptInput.scrollHeight}px`
  }

  const [userQuery, setPrompt] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!userQuery.trim()) return

    const prompt = userQuery.trim()
    const token = localStorage.getItem('token')

    try {
      const response = await axios.post(
        'http://localhost:5000/llm_response',
        {
          user_query: prompt,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      setMessages((prev) => [
        ...prev,
        { role: 'user', text: prompt },
        { role: 'assistant', text: response.data.message },
      ])
      setPrompt('')
      e.target.reset()
    } catch (error) {
      console.log(error.response?.data || error.message)
    }
  }

  return (
    <footer className="prompt-composer">
      <form className="prompt-form" onSubmit={handleSubmit}>
        <textarea
          className="prompt-input form-control"
          rows="1"
          aria-label="Message prompt"
          placeholder="Message PromptGuard..."
          value={userQuery}
          onInput={handlePromptInput}
          onChange={(e) => setPrompt(e.target.value)}
        />

        <button type="submit" className="prompt-submit btn">
          Send
        </button>
      </form>
    </footer>
  )
}

export default Footer
