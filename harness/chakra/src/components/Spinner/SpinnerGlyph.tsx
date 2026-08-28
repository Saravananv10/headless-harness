import * as React from 'react';
import { Box, Text, useTheme } from '../../ink.js';
import { stringWidth } from '../../ink/stringWidth.js';
import { getTheme, type Theme } from '../../utils/theme.js';
import { FALLBACK_SPINNER_FRAMES, interpolateColor, parseRGB, toRGBColor } from './utils.js';

const REDUCED_MOTION_DOT = '●';
const REDUCED_MOTION_CYCLE_MS = 2000; // 2-second cycle: 1s visible, 1s dim
const ERROR_RED = {
  r: 171,
  g: 43,
  b: 63,
};

type Props = {
  frame: number;
  messageColor: keyof Theme;
  stalledIntensity?: number;
  reducedMotion?: boolean;
  time?: number;
  /** Full forward animation cycle; defaults to braille orbit. */
  frames?: string[];
};

export function SpinnerGlyph({
  frame,
  messageColor,
  stalledIntensity = 0,
  reducedMotion = false,
  time = 0,
  frames = FALLBACK_SPINNER_FRAMES,
}: Props): React.ReactNode {
  const [themeName] = useTheme();
  const theme = getTheme(themeName);
  const spinnerChar = frames[frame % frames.length] ?? '·';
  const cellW = Math.max(2, stringWidth(spinnerChar));

  if (reducedMotion) {
    const isDim = Math.floor(time / (REDUCED_MOTION_CYCLE_MS / 2)) % 2 === 1;
    return (
      <Box flexWrap="wrap" height={1} width={cellW}>
        <Text color={messageColor} dimColor={isDim}>
          {REDUCED_MOTION_DOT}
        </Text>
      </Box>
    );
  }

  if (stalledIntensity > 0) {
    const baseColorStr = theme[messageColor];
    const baseRGB = baseColorStr ? parseRGB(baseColorStr) : null;
    if (baseRGB) {
      const interpolated = interpolateColor(baseRGB, ERROR_RED, stalledIntensity);
      return (
        <Box flexWrap="wrap" height={1} width={cellW}>
          <Text color={toRGBColor(interpolated)}>{spinnerChar}</Text>
        </Box>
      );
    }
    const color = stalledIntensity > 0.5 ? 'error' : messageColor;
    return (
      <Box flexWrap="wrap" height={1} width={cellW}>
        <Text color={color}>{spinnerChar}</Text>
      </Box>
    );
  }

  return (
    <Box flexWrap="wrap" height={1} width={cellW}>
      <Text color={messageColor}>{spinnerChar}</Text>
    </Box>
  );
}
