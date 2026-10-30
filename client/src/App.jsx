import React, { useState } from 'react'
import Header from './assets/Components/Header'
import Login from './assets/Pages/Login'
import Dashboard from './assets/Pages/Dashboard'
import './App.css'
import Footer from './assets/Components/Footer'

function App() {
  const token = localStorage.getItem('token')
  const [messages, setMessages] = useState([])

  return (
    <div className="app-shell">
      <Header />
      <main className={`page-shell ${token ? 'page-shell--logged-in' : ''}`}>
        {token ? (
          <>
            <Dashboard messages={messages} />
            <Footer setMessages={setMessages} />
          </>
        ) : (
          <Login />
        )}
      </main>
    </div>
  )
}

export default App
