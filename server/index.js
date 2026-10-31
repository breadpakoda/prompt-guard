const cors = require('cors')
const express = require('express')
const app = express()
app.use(cors())
app.use(express.json())

const jwt = require('jsonwebtoken')
const axios = require('axios')
const { MongoClient } = require('mongodb')
const authenticationToken = require('./auth')

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017'
const MONGODB_DB = process.env.MONGODB_DB || 'prompt_guard'

let mongoClient = null
let conversationCollection = null

async function getConversationCollection() {
  if (conversationCollection) return conversationCollection

  mongoClient = new MongoClient(MONGODB_URI)
  await mongoClient.connect()

  const db = mongoClient.db(MONGODB_DB)
  conversationCollection = db.collection('messages')
  return conversationCollection
}

async function saveMessage(email, role, text) {
  try {
    const collection = await getConversationCollection()
    await collection.insertOne({
      email,
      role,
      text,
      createdAt: new Date(),
    })
  } catch (error) {
    console.log('MongoDB write failed:', error.message)
  }
}

async function getRecentMessages(email, limit = 20) {
  try {
    const collection = await getConversationCollection()
    const docs = await collection
      .find({ email })
      .sort({ createdAt: 1 })
      .limit(limit)
      .toArray()

    return docs.map((doc) => ({
      role: doc.role,
      content: doc.text,
    }))
  } catch (error) {
    console.log('MongoDB read failed:', error.message)
    return []
  }
}

app.post('/login', (req, res) => {
  const { email, password } = req.body
  const email_c = 'adityasing272@gmail.com'
  const password_c = 'asdfghjkl'

  if (email === email_c && password === password_c) {
    const token = jwt.sign({
      user_id: '1234',
      email,
    }, 'JWT_SECRET', { expiresIn: '1h' })

    return res.status(200).json({
      message: 'Logged in successfully',
      token,
    })
  }

  return res.status(401).json({
    message: 'Invalid credentials',
  })
})

app.get('/dashboard', authenticationToken, (req, res) => {
  res.json({
    message: 'Dashboard accessed successfully',
    email: req.user.email,
  })
})

app.post('/llm_response', authenticationToken, async (req, res) => {
  const { user_query } = req.body
  const email = req.user.email

  if (!user_query || !user_query.trim()) {
    return res.status(400).json({
      message: 'Prompt is required',
    })
  }

  const cleanQuery = user_query.trim()
  const history = await getRecentMessages(email)

  try {
    const response = await axios.post('http://localhost:8000/chat', {
      prompt: cleanQuery,
      conversation: history,
    })

    await saveMessage(email, 'user', cleanQuery)
    await saveMessage(email, 'assistant', response.data.answer)

    return res.status(200).json({
      message: response.data.answer,
    })
  } catch (error) {
    console.log('LLM request failed:', error.message)
    return res.status(500).json({
      message: 'Unable to process the request right now.',
    })
  }
})

app.listen(5000, () => console.log('Server running'))
