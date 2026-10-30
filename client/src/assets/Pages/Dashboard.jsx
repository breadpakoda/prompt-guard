import React, { useEffect, useState } from 'react'
import axios from 'axios'

function Dashboard({ messages }) {
  const [email, setEmail] = useState('')

  useEffect(() => {
    const getDashboard = async () => {
      const token = localStorage.getItem('token')

      try {
        const response = await axios.get('http://localhost:5000/dashboard', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })

        setEmail(response.data.email)
      } catch (error) {
        console.log(error.response?.data)
      }
    }

    getDashboard()
  }, [])

  return (
    <main className="dashboard-page">
      <div className="dashboard-topbar">
        <span className="eyebrow">Dashboard</span>
        <h1 className="dashboard-title">{email || 'User'}</h1>
      </div>

      <section className="dashboard-box">
        <div className="chat-thread">
          {messages.length === 0 ? (
            <p className="dashboard-empty">Your prompt and AI response will appear here.</p>
          ) : (
            messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`message-row ${message.role === 'user' ? 'message-row--user' : 'message-row--assistant'}`}
              >
                <div className={`message-bubble ${message.role === 'user' ? 'message-bubble--user' : 'message-bubble--assistant'}`}>
                  {message.text}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </main>
  )
}

export default Dashboard
