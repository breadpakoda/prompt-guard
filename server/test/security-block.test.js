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

test('persists a malicious security alert and rejects later prompts', async () => {
  const created = await createConversation()
  conversationId = created.conversationId
  assert.equal(created.result.status, 201)

  const alert = await request('/layer3-alert', {
    method: 'POST',
    body: {
      conversation_id: conversationId,
      is_malicious: true,
      reason: 'Automated integration test',
    },
  })
  assert.equal(alert.status, 202)
  assert.equal(alert.body.security_status, 'blocked')

  const history = await request(`/conversations/${conversationId}`)
  assert.equal(history.body.security_status, 'blocked')

  const blockedRequest = await request('/llm_response', {
    method: 'POST',
    body: { conversation_id: conversationId, prompt: 'A later benign prompt.' },
  })
  assert.equal(blockedRequest.status, 403)
  assert.equal(blockedRequest.body.security_status, 'blocked')

  const nonMaliciousAlert = await request('/layer3-alert', {
    method: 'POST',
    body: {
      conversation_id: conversationId,
      is_malicious: false,
      reason: 'A later clear result must not reset a prior block',
    },
  })
  assert.equal(nonMaliciousAlert.status, 202)

  const promptDetectionAlert = await request('/security-alert', {
    method: 'POST',
    body: {
      conversation_id: conversationId,
      is_malicious: true,
      alert_type: 'prompt_injection',
      layer1_score: 0.9,
      layer2_score: 0.2,
      combined_score: 0.9,
    },
  })
  assert.equal(promptDetectionAlert.status, 202)

  const unchangedHistory = await request(`/conversations/${conversationId}`)
  assert.equal(unchangedHistory.body.security_status, 'blocked')
  assert.equal(unchangedHistory.body.messages.length, 0)
})

test('Layer 1/2 alerts report detections without blocking clear conversations', async () => {
  const created = await createConversation()
  try {
    const alert = await request('/security-alert', {
      method: 'POST',
      body: {
        conversation_id: created.conversationId,
        is_malicious: true,
        alert_type: 'prompt_injection',
        layer1_score: 0.99,
        layer2_score: 0.2,
        combined_score: 0.99,
      },
    })

    assert.equal(alert.status, 202)
    assert.equal(alert.body.security_status, 'clear')

    const history = await request(`/conversations/${created.conversationId}`)
    assert.equal(history.body.security_status, 'clear')
  } finally {
    await cleanupConversation(created.conversationId)
  }
})
