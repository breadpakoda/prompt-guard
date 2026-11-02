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

test('accepts multiple prompts and persists the ordered chat history', async () => {
  const created = await createConversation()
  conversationId = created.conversationId
  assert.equal(created.result.status, 201)
  assert.equal(created.result.body.conversation_id, conversationId)
  assert.equal(created.result.body.security_status, 'clear')

  const prompts = [
    'Give me one short fact about Saturn.',
    'What is 17 times 24?',
  ]

  for (const prompt of prompts) {
    const result = await request('/llm_response', {
      method: 'POST',
      body: { conversation_id: conversationId, prompt },
    })
    assert.equal(result.status, 200, JSON.stringify(result.body))
    assert.equal(result.body.conversation_id, conversationId)
    assert.equal(typeof result.body.response, 'string')
    assert.ok(result.body.response.trim().length > 0)
  }

  const greetingResponse = await request('/llm_response', {
    method: 'POST',
    body: { conversation_id: conversationId, prompt: 'hi' },
  })
  assert.equal(greetingResponse.status, 200, JSON.stringify(greetingResponse.body))
  assert.equal(greetingResponse.body.security_status, 'clear')
  assert.notEqual(
    greetingResponse.body.response,
    "A prompt injection attempt was detected. This request can't be fulfilled."
  )

  const history = await request(`/conversations/${conversationId}`)
  assert.equal(history.status, 200)
  assert.deepEqual(
    history.body.messages.map(({ role, content }) => ({ role, content })),
    [
      { role: 'user', content: prompts[0] },
      { role: 'assistant', content: history.body.messages[1].content },
      { role: 'user', content: prompts[1] },
      { role: 'assistant', content: history.body.messages[3].content },
      { role: 'user', content: 'hi' },
      { role: 'assistant', content: history.body.messages[5].content },
    ]
  )
  assert.equal(history.body.messages.length, 6)
  assert.ok(new Date(history.body.updated_at) >= new Date(history.body.created_at))

  const concurrentPrompts = [
    'What is the largest planet in our solar system?',
    'What color do you get by mixing blue and yellow?',
  ]
  const concurrentResponses = await Promise.all(
    concurrentPrompts.map((prompt) =>
      request('/llm_response', {
        method: 'POST',
        body: { conversation_id: conversationId, prompt },
      })
    )
  )

  assert.ok(concurrentResponses.every((result) => result.status === 200))
  const concurrentHistory = await request(`/conversations/${conversationId}`)
  assert.equal(concurrentHistory.body.messages.length, 10)
  assert.deepEqual(
    concurrentHistory.body.messages.slice(6).filter(({ role }) => role === 'user').map(({ content }) => content),
    concurrentPrompts
  )
  assert.deepEqual(
    concurrentHistory.body.messages.slice(6).map(({ role }) => role),
    ['user', 'assistant', 'user', 'assistant']
  )
})
