import React, { useState } from 'react'
import TextInput from './TextInput.js'
import { Box, Text } from '../ink.js'
import { useTerminalSize } from '../hooks/useTerminalSize.js'

type Props = {
  onDone: (apiKey: string) => void
}

export function SoketApiKeyDialog({ onDone }: Props): React.ReactNode {
  const [value, setValue] = useState('')
  const [cursorOffset, setCursorOffset] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const terminalSize = useTerminalSize()

  function submit(raw: string): void {
    const key = raw.trim()
    if (!key) {
      setError('API key is required to continue.')
      return
    }
    onDone(key)
  }

  return (
    <Box flexDirection="column" paddingLeft={1}>
      <Text bold>Soket API key required</Text>
      <Text dimColor>Enter your key to continue. It will be saved to ~/.chakra/soket_api_key.</Text>
      <Box marginTop={1}>
        <TextInput
          value={value}
          onChange={next => {
            setValue(next)
            if (error) setError(null)
          }}
          onSubmit={submit}
          onPaste={pastedText => {
            const before = value.slice(0, cursorOffset)
            const after = value.slice(cursorOffset)
            const next = before + pastedText + after
            setValue(next)
            setCursorOffset(before.length + pastedText.length)
          }}
          focus
          showCursor
          mask="*"
          placeholder="sk-..."
          columns={terminalSize.columns}
          cursorOffset={cursorOffset}
          onChangeCursorOffset={setCursorOffset}
        />
      </Box>
      {error ? (
        <Box marginTop={1}>
          <Text color="error">{error}</Text>
        </Box>
      ) : null}
      <Box marginTop={1}>
        <Text dimColor>Press Enter to save and continue</Text>
      </Box>
    </Box>
  )
}
