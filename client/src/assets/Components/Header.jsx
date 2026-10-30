import React from 'react'

function Header() {
  const handleLogout = () => {
    localStorage.removeItem('token')
    window.location.reload()
  }

  const token = localStorage.getItem('token')

  return (
    <nav className="navbar">
      <div className="container-fluid">
        <a className="navbar-brand" href="#">Prompt-Guard</a>

        {token && (
          <button type="button" className="logout-button" onClick={handleLogout}>
            Sign Out
          </button>
        )}
      </div>
    </nav>
  )
}

export default Header
