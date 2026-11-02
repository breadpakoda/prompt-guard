const path = require('path')
const { randomUUID } = require('crypto')
const { MongoClient } = require('mongodb')

require('dotenv').config({ path: path.resolve(__dirname, '../../.env') })

const API_BASE_URL = process.env.TEST_API_BASE_URL || 'http://localhost:5000'
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017'
const MONGODB_DB = process.env.MONGODB_DB || 'prompt_guard'

async function request(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: options.method || 'GET',
    headers: options.body ? { 'content-type': 'application/json' } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  const body = await response.json()
  return { status: response.status, body }
}

async function createConversation() {
  const conversationId = `test-${randomUUID()}`
  const result = await request('/conversations', {
    method: 'POST',
    body: { conversation_id: conversationId },
  })

  return { conversationId, result }
}

async function cleanupConversation(conversationId) {
  const client = new MongoClient(MONGODB_URI)
  try {
    await client.connect()
    await client.db(MONGODB_DB).collection('conversations').deleteOne({
      conversation_id: conversationId,
    })
  } finally {
    await client.close()
  }
}

async function setConversationSecurityStatus(conversationId, securityStatus) {
  const client = new MongoClient(MONGODB_URI)
  try {
    await client.connect()
    await client.db(MONGODB_DB).collection('conversations').updateOne(
      { conversation_id: conversationId },
      { $set: { security_status: securityStatus } }
    )
  } finally {
    await client.close()
  }
}

module.exports = {
  cleanupConversation,
  createConversation,
  request,
  setConversationSecurityStatus,
}
