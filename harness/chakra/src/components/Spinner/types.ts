export type RGBColor = {
  r: number
  g: number
  b: number
}

export type SpinnerMode =
  | 'requesting'
  | 'thinking'
  | 'responding'
  | 'tool-use'
  | 'tool-input'
