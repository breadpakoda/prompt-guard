const path = require('path')
const cors = require('cors')
const express = require('express')
const axios = require('axios')
const { MongoClient } = require('mongodb')
const { randomUUID } = require('crypto')
require('dotenv').config({ path: path.resolve(__dirname, '../.env') })

const app = express()
app.use(cors())
app.use(express.json())

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017'
const MONGODB_DB = process.env.MONGODB_DB || 'prompt_guard'
const FASTAPI_BASE_URL = process.env.AI_ENGINE_URL || 'http://localhost:8000'

let mongoClient = null
let conversationCollection = null
const conversationLocks = new Map()

async function getConversationCollection() {
  if (conversationCollection) return conversationCollection

  mongoClient = new MongoClient(MONGODB_URI)
  await mongoClient.connect()

  const db = mongoClient.db(MONGODB_DB)
  conversationCollection = db.collection('conversations')

  await conversationCollection.createIndex({ conversation_id: 1 }, { unique: true })
  await conversationCollection.createIndex({ updated_at: -1 })

  return conversationCollection
}

function buildConversationSummary(doc) {
  const messages = Array.isArray(doc.messages) ? doc.messages : []
  const previewMessage = messages
    .slice()
    .reverse()
    .find((message) => message && message.content && String(message.content).trim())

  return {
    conversation_id: doc.conversation_id,
    security_status: doc.security_status || 'clear',
    created_at: doc.created_at,
    updated_at: doc.updated_at,
    title: previewMessage
      ? (previewMessage.role === 'user' ? 'User prompt' : 'Assistant reply')
      : 'New chat',
    preview: previewMessage ? previewMessage.content : 'No messages yet',
    messages,
  }
}

function isLocalRequest(req) {
  return ['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.ip)
}

async function getOrCreateConversation(conversationId) {
  const collection = await getConversationCollection()
  const now = new Date()
  await collection.updateOne(
    { conversation_id: conversationId },
    {
      $setOnInsert: {
        conversation_id: conversationId,
        messages: [],
        security_status: 'clear',
        created_at: now,
        updated_at: now,
      },
    },
    { upsert: true }
  )

  return collection.findOne({ conversation_id: conversationId })
}

async function blockConversation(conversationId) {
  const collection = await getConversationCollection()
  await collection.updateOne(
    { conversation_id: conversationId },
    {
      $set: {
        security_status: 'blocked',
        updated_at: new Date(),
      },
      $setOnInsert: {
        messages: [],
        created_at: new Date(),
      },
    },
    { upsert: true }
  )
}

async function markConversationPending(conversationId) {
  const collection = await getConversationCollection()
  await collection.updateOne(
    { conversation_id: conversationId, security_status: { $ne: 'blocked' } },
    {
      $set: {
        security_status: 'pending',
        updated_at: new Date(),
      },
    }
  )
}

async function refreshPendingStatus(conversationId) {
  const response = await axios.get(
    `${FASTAPI_BASE_URL}/status/${encodeURIComponent(conversationId)}`,
    { timeout: 5000 }
  )
  const status = response.data?.security_status

  if (!['clear', 'blocked', 'pending'].includes(status)) {
    throw new Error('AI engine returned an invalid conversation security status')
  }

  if (status === 'blocked') {
    await blockConversation(conversationId)
    return 'blocked'
  }

  if (status === 'clear') {
    const collection = await getConversationCollection()
    await collection.updateOne(
      { conversation_id: conversationId, security_status: 'pending' },
      { $set: { security_status: 'clear', updated_at: new Date() } }
    )
  }

  const conversation = await getConversationHistory(conversationId)
  return conversation.security_status || 'clear'
}

async function withConversationLock(conversationId, operation) {
  const previous = conversationLocks.get(conversationId) || Promise.resolve()
  let release
  const current = new Promise((resolve) => {
    release = resolve
  })
  const tail = previous.then(() => current)
  conversationLocks.set(conversationId, tail)

  await previous
  try {
    return await operation()
  } finally {
    release()
    if (conversationLocks.get(conversationId) === tail) {
      conversationLocks.delete(conversationId)
    }
  }
}

async function appendMessage(conversationId, role, content) {
  const collection = await getConversationCollection()
  const message = {
    role,
    content,
    timestamp: new Date().toISOString(),
  }

  await collection.updateOne(
    { conversation_id: conversationId },
    {
      $push: { messages: message },
      $set: { updated_at: new Date() },
    },
    { upsert: true }
  )
}

async function getConversationHistory(conversationId) {
  const collection = await getConversationCollection()
  const conversation = await collection.findOne({ conversation_id: conversationId })
  return conversation || { conversation_id: conversationId, messages: [], security_status: 'clear' }
}

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'prompt-guard-node' })
})

app.post('/conversations', async (req, res) => {
  const requestedId = typeof req.body?.conversation_id === 'string' && req.body.conversation_id.trim()
    ? req.body.conversation_id.trim()
    : randomUUID()

  const conversation = await getOrCreateConversation(requestedId)
  return res.status(201).json(buildConversationSummary(conversation))
})

app.get('/conversations', async (req, res) => {
  try {
    const collection = await getConversationCollection()
    const conversations = await collection
      .find({})
      .sort({ updated_at: -1 })
      .toArray()

    return res.json(conversations.map(buildConversationSummary))
  } catch (error) {
    console.error('Failed to list conversations:', error)
    return res.status(500).json({ message: 'Unable to load conversations.' })
  }
})

app.get('/conversations/:conversation_id', async (req, res) => {
  try {
    const conversation = await getConversationHistory(req.params.conversation_id)
    return res.json(buildConversationSummary(conversation))
  } catch (error) {
    console.error('Failed to fetch conversation:', error)
    return res.status(500).json({ message: 'Unable to load conversation.' })
  }
})

async function handleLayer3Alert(req, res) {
  const { conversation_id, is_malicious, reason } = req.body || {}

  if (!isLocalRequest(req)) {
    return res.status(403).json({ message: 'Security alerts are internal only' })
  }

  if (typeof conversation_id !== 'string' || !conversation_id.trim()) {
    return res.status(400).json({ message: 'Invalid conversation_id' })
  }

  if (typeof is_malicious !== 'boolean') {
    return res.status(400).json({ message: 'is_malicious must be a boolean' })
  }

  if (is_malicious === true) {
    await blockConversation(conversation_id)
    console.warn(`Security alert received for ${conversation_id}: ${reason || 'prompt_injection'}`)
  }

  const conversation = await getConversationHistory(conversation_id)
  return res.status(202).json({
    status: is_malicious ? 'alert_received' : 'alert_processed',
    conversation_id,
    security_status: conversation.security_status || 'clear',
  })
}

async function handlePromptDetectionAlert(req, res) {
  const {
    conversation_id,
    is_malicious,
    alert_type,
    layer1_score,
    layer2_score,
    combined_score,
  } = req.body || {}
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
  const localRequest = isLocalRequest(req)

  if (
    !localRequest ||
    typeof conversation_id !== 'string' ||
    !conversation_id.trim() ||
    is_malicious !== true ||
    alert_type !== 'prompt_injection' ||
    !validScores
  ) {
    return res.status(localRequest ? 400 : 403).json({
      message: localRequest ? 'Invalid prompt-detection alert' : 'Security alerts are internal only',
    })
  }

  const conversation = await getConversationHistory(conversation_id)
  console.warn(`Layer 1/2 prompt detection received for ${conversation_id}`)
  return res.status(202).json({
    status: 'alert_received',
    conversation_id,
    security_status: conversation.security_status || 'clear',
  })
}

app.post('/security-alert', handlePromptDetectionAlert)
app.post('/layer3-alert', handleLayer3Alert)

app.post('/llm_response', async (req, res) => {
  const body = req.body || {}
  const promptText = typeof body.prompt === 'string' ? body.prompt : body.user_query
  const conversationId = typeof body.conversation_id === 'string' ? body.conversation_id : null

  if (typeof conversationId !== 'string' || !conversationId.trim()) {
    return res.status(400).json({ message: 'A valid conversation_id is required.' })
  }

  if (typeof promptText !== 'string' || !promptText.trim()) {
    return res.status(400).json({ message: 'Prompt is required.' })
  }

  return withConversationLock(conversationId, async () => {
    try {
      const conversation = await getOrCreateConversation(conversationId)

      if (conversation.security_status === 'blocked') {
        return res.status(403).json({
          message: 'This conversation has been blocked due to a security violation.',
          security_status: 'blocked',
        })
      }

      if (conversation.security_status === 'pending') {
        let currentStatus
        try {
          currentStatus = await refreshPendingStatus(conversationId)
        } catch (statusError) {
          console.error('Unable to resolve pending security status:', statusError.message)
          return res.status(503).json({
            message: 'The security status could not be verified. No prompt was sent; please retry shortly.',
            security_status: 'pending',
          })
        }

        if (currentStatus === 'blocked') {
          return res.status(403).json({
            message: 'This conversation has been blocked due to a security violation.',
            security_status: 'blocked',
          })
        }

        if (currentStatus === 'pending') {
          return res.status(503).json({
            message: 'A security check is still in progress. No prompt was sent; please retry shortly.',
            security_status: 'pending',
          })
        }
      }

      const response = await axios.post(
        `${FASTAPI_BASE_URL}/chat`,
        {
          conversation_id: conversationId,
          prompt: promptText.trim(),
        },
        { timeout: 30000 }
      )

      const aiData = response.data || {}
      const answer = aiData.response || aiData.message || 'No response received.'

      await appendMessage(conversationId, 'user', promptText.trim())
      await appendMessage(conversationId, 'assistant', answer)

      if (aiData.l3_result === true) {
        await blockConversation(conversationId)
      }

      const updatedConversation = await getConversationHistory(conversationId)
      const securityStatus = updatedConversation.security_status || 'clear'
      const result = {
        conversation_id: conversationId,
        response: answer,
        message: answer,
        security_status: securityStatus,
      }

      if (aiData.l3_result === true || securityStatus === 'blocked') {
        result.security_warning =
          'Suspicious activity detected. This conversation has been blocked.'
      } else if (aiData.prompt_injection_detected) {
        result.security_warning =
          'Prompt injection was detected. This request was refused; you can continue in this conversation.'
      }

      return res.status(200).json(result)
    } catch (error) {
      if (error.response) {
        const status = error.response.status
        const detail = error.response.data?.detail || {}

        if (status === 403) {
          await blockConversation(conversationId)
          return res.status(403).json({
            message: detail.message || 'This conversation has been blocked due to a security violation.',
            security_status: 'blocked',
          })
        }

        if (status === 503) {
          await markConversationPending(conversationId)
          return res.status(503).json({
            message: detail.message || 'A security check is in progress. Please try again in a moment.',
            security_status: 'pending',
          })
        }
      }

      console.error('LLM request failed:', error.message)
      return res.status(500).json({
        message: 'Unable to process the request right now.',
      })
    }
  })
})

app.listen(5000, () => {
  console.log('Node server running on http://localhost:5000')
})
