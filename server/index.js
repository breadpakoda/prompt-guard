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

app.post('/security-alert', (req, res) => {
  const {
    conversation_id,
    is_malicious,
    alert_type,
    reason,
    layer1_score,
    layer2_score,
    combined_score,
  } = req.body

  const isLocalRequest = ['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.ip)
  const validScores =
    Number.isFinite(layer1_score) &&
    layer1_score >= 0 &&
    layer1_score <= 1 &&
    Number.isFinite(layer2_score) &&
    layer2_score >= -1 &&
    layer2_score <= 1 &&
    Number.isFinite(combined_score) &&
    combined_score >= 0 &&
    combined_score <= 1

  if (!isLocalRequest) {
    return res.status(403).json({ message: 'Security alerts are internal only' })
  }

  if (
    typeof conversation_id !== 'string' ||
    !conversation_id.trim() ||
    is_malicious !== true ||
    alert_type !== 'prompt_injection' ||
    !validScores
  ) {
    return res.status(400).json({ message: 'Invalid security alert' })
  }

  console.warn('Prompt injection alert received:', {
    reason,
    layer1_score,
    layer2_score,
    combined_score,
  })

  return res.status(202).json({ status: 'alert_received' })
})

// ── Main chatbot endpoint ─────────────────────────────────────────────────────
// The Python service scores Layer 1 and Layer 2 together before forwarding
// accepted prompts to the target LLM. This endpoint also enforces Layer-3
// conversation blocks.

app.post('/llm_response', authenticationToken, async (req, res) => {
  const { user_query } = req.body
  const email = req.user.email

  if (!user_query || !user_query.trim()) {
    return res.status(400).json({ message: 'Prompt is required' })
  }

  const cleanQuery = user_query.trim()

  try {
    // Forward to the Python FastAPI LLM service.
    // The email is used as the stable conversation_id so each user has
    // their own isolated conversation history and security state.
    const response = await axios.post('http://localhost:8000/chat', {
      prompt: cleanQuery,
      conversation_id: email,
    })

    const {
      response: answer,
      l3_triggered,
      l3_result,
      prompt_injection_detected,
      layer1_score,
      layer2_score,
      combined_score,
    } = response.data

    // Persist to MongoDB for chat-history display in the client
    await saveMessage(email, 'user', cleanQuery)
    await saveMessage(email, 'assistant', answer)

    // Warn the client on the turn that Layer 3 just flagged the conversation.
    // Subsequent requests will be rejected with 403.
    if (l3_triggered && l3_result === true) {
      return res.status(200).json({
        message: answer,
        security_warning:
          'Suspicious activity detected. This conversation has been blocked.',
      })
    }

    if (prompt_injection_detected) {
      return res.status(200).json({
        message: answer,
        security_warning: 'Prompt injection attempt detected. This request cannot be fulfilled.',
        prompt_injection_detected: true,
        layer1_score,
        layer2_score,
        combined_score,
      })
    }

    return res.status(200).json({ message: answer })

  } catch (error) {
    if (error.response) {
      const httpStatus = error.response.status
      const detail = error.response.data?.detail || {}

      // 403 — conversation permanently blocked by Layer 3
      if (httpStatus === 403) {
        return res.status(403).json({
          message:
            detail.message ||
            'This conversation has been blocked due to a security violation.',
        })
      }

      // 503 — Layer-3 check still in progress; tell the client to retry
      if (httpStatus === 503) {
        return res.status(503).json({
          message:
            'A security check is in progress. Please try again in a moment.',
        })
      }
    }

    console.error('LLM request failed:', error.message)
    return res.status(500).json({
      message: 'Unable to process the request right now.',
    })
  }
})

app.listen(5000, () => console.log('Server running'))
