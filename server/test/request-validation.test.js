const assert = require('node:assert/strict')
const { after, test } = require('node:test')
const {
  cleanupConversation,
  createConversation,
  request,
} = require('./helpers')

let conversationId

after(async () => {
  if (conversationId) {
    await cleanupConversation(conversationId)
  }
})

test('rejects missing conversation IDs and empty prompts without saving messages', async () => {
  const missingId = await request('/llm_response', {
    method: 'POST',
    body: { prompt: 'A valid prompt without a conversation ID.' },
  })
  assert.equal(missingId.status, 400)

  const created = await createConversation()
  conversationId = created.conversationId
  assert.equal(created.result.status, 201)

  const emptyPrompt = await request('/llm_response', {
    method: 'POST',
    body: { conversation_id: conversationId, prompt: '   ' },
  })
  assert.equal(emptyPrompt.status, 400)

  const history = await request(`/conversations/${conversationId}`)
  assert.equal(history.status, 200)
  assert.equal(history.body.messages.length, 0)
  assert.equal(history.body.security_status, 'clear')
})
