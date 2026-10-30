import axios from 'axios';
import {useState} from 'react';

function Login() {

  const [email,setemail]=useState("");
  const [password,setpassword]=useState("");

  
  

  const handlesubmit=async(e)=>{
    e.preventDefault();
    try{
      const response = await axios.post("http://localhost:5000/login",{
      email,
      password
    })
    console.log(response.data.message)


    localStorage.setItem("token",response.data.token)
    const token = localStorage.getItem("token");

if (token) {
  window.location.reload();
  console.log("Logged in");
}
    }
    catch(error){
      console.log(error)
    }
    
  }
  return (
    <main className="login-page">
        <section className="login-card">
          <div className="login-heading">
            <span className="eyebrow">WELCOME BACK</span>
            <h1>Sign in to your workspace</h1>
            <p>Keep your prompts protected and your ideas moving.</p>
          </div>
          <form onSubmit={handlesubmit}>
            <div className="field-group">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  value={email}
                  type="email"
                  placeholder="Email..."
                  onChange={(e)=>setemail(e.target.value)}
                />
            </div>
              <div className="field-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  value={password}
                  type="password"
                  placeholder="Password..."
                  onChange={(e)=>setpassword(e.target.value)}
                />
            </div>
            <button className="login-button" type="submit">Continue <span aria-hidden="true">→</span></button>
          </form>
          <p className="login-note"><span aria-hidden="true">●</span> Your session is encrypted</p>
        </section>
    </main>
  )
}

export default Login
