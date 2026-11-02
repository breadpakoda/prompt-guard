const assert = require('node:assert/strict')
const { after, test } = require('node:test')
const {
  cleanupConversation,
  createConversation,
  request,
  setConversationSecurityStatus,
} = require('./helpers')

let conversationId

after(async () => {
  if (conversationId) {
    await cleanupConversation(conversationId)
  }
})

test('rechecks pending status with FastAPI and resumes only after it clears', async () => {
  const created = await createConversation()
  conversationId = created.conversationId
  assert.equal(created.result.status, 201)

  const aiSeed = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, prompt: 'hi' }),
  })
  assert.equal(aiSeed.status, 200)

  await setConversationSecurityStatus(conversationId, 'pending')
  const response = await request('/llm_response', {
    method: 'POST',
    body: { conversation_id: conversationId, prompt: 'What is 2 plus 2?' },
  })

  assert.equal(response.status, 200, JSON.stringify(response.body))
  assert.equal(response.body.security_status, 'clear')

  const history = await request(`/conversations/${conversationId}`)
  assert.equal(history.body.security_status, 'clear')
  assert.equal(history.body.messages.length, 2)
})
