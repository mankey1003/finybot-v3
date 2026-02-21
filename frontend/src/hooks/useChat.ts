import { useCallback, useRef, useState } from 'react'
import { api, apiStream } from '../lib/api'

export interface ToolCall {
  name: string
  arguments: Record<string, unknown>
  result: string | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string | null
  toolCalls: ToolCall[] | null
  created_at?: string
}

interface Chat {
  id: string
  title: string
  created_at?: string
  updated_at?: string
}

interface ChatListResponse {
  chats: Chat[]
}

export function useChat() {
  const [chats, setChats] = useState<Chat[]>([])
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const loadChats = useCallback(async () => {
    try {
      const data = await api<ChatListResponse>('/api/chat')
      setChats(data.chats)
    } catch (e: any) {
      setError(e.message)
    }
  }, [])

  const loadMessages = useCallback(async (chatId: string) => {
    try {
      setCurrentChatId(chatId)
      const msgs = await api<ChatMessage[]>(`/api/chat/${chatId}/messages`)
      setMessages(msgs)
      setError(null)
    } catch (e: any) {
      setError(e.message)
    }
  }, [])

  const startNewChat = useCallback(() => {
    setCurrentChatId(null)
    setMessages([])
    setError(null)
  }, [])

  const deleteChat = useCallback(async (chatId: string) => {
    try {
      await api(`/api/chat/${chatId}`, { method: 'DELETE' })
      setChats(prev => prev.filter(c => c.id !== chatId))
      if (currentChatId === chatId) {
        setCurrentChatId(null)
        setMessages([])
      }
    } catch (e: any) {
      setError(e.message)
    }
  }, [currentChatId])

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
  }, [])

  const sendMessage = useCallback(async (text: string) => {
    setError(null)
    setIsStreaming(true)

    // Add user message to UI immediately
    const userMsg: ChatMessage = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: text,
      toolCalls: null,
    }
    setMessages(prev => [...prev, userMsg])

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await apiStream('/api/chat/send', {
        message: text,
        conversation_id: currentChatId,
      }, controller.signal)

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      // Track tool calls for the current assistant response
      let pendingToolCalls: ToolCall[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ') && eventType) {
            const data = JSON.parse(line.slice(6))

            switch (eventType) {
              case 'chat_id':
                setCurrentChatId(data.chat_id)
                break

              case 'tool_call':
                pendingToolCalls.push({
                  name: data.name,
                  arguments: data.arguments,
                  result: null,
                })
                // Add/update a pending assistant message showing tool calls in progress
                setMessages(prev => {
                  const last = prev[prev.length - 1]
                  if (last?.role === 'assistant' && last.id.startsWith('temp-assistant')) {
                    return [
                      ...prev.slice(0, -1),
                      { ...last, toolCalls: [...pendingToolCalls] },
                    ]
                  }
                  return [
                    ...prev,
                    {
                      id: `temp-assistant-${Date.now()}`,
                      role: 'assistant',
                      content: null,
                      toolCalls: [...pendingToolCalls],
                    },
                  ]
                })
                break

              case 'tool_result':
                // Update the last tool call with its result
                pendingToolCalls = pendingToolCalls.map(tc =>
                  tc.name === data.name && tc.result === null
                    ? { ...tc, result: data.result }
                    : tc
                )
                setMessages(prev => {
                  const last = prev[prev.length - 1]
                  if (last?.role === 'assistant' && last.id.startsWith('temp-assistant')) {
                    return [
                      ...prev.slice(0, -1),
                      { ...last, toolCalls: [...pendingToolCalls] },
                    ]
                  }
                  return prev
                })
                break

              case 'message':
                setMessages(prev => {
                  const last = prev[prev.length - 1]
                  if (last?.role === 'assistant' && last.id.startsWith('temp-assistant')) {
                    return [
                      ...prev.slice(0, -1),
                      { ...last, content: data.content, toolCalls: data.tool_calls?.length ? data.tool_calls : last.toolCalls },
                    ]
                  }
                  return [
                    ...prev,
                    {
                      id: `temp-assistant-${Date.now()}`,
                      role: 'assistant',
                      content: data.content,
                      toolCalls: data.tool_calls?.length ? data.tool_calls : null,
                    },
                  ]
                })
                break

              case 'error':
                setError(data.message)
                break
            }
            eventType = ''
          }
        }
      }

      // Refresh chat list to pick up new/updated chat
      loadChats()

    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setError(e.message)
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [currentChatId, loadChats])

  return {
    chats,
    currentChatId,
    messages,
    isStreaming,
    error,
    loadChats,
    loadMessages,
    sendMessage,
    startNewChat,
    stopStreaming,
    deleteChat,
  }
}
