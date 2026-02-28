// Cesium 1.138 post-process GLSL — WebGL2 (GLSL 300 ES)
// Rules: no helper functions (inline everything), out_FragColor for output,
// colorTexture and v_textureCoordinates are auto-provided by Cesium.

export const CRT_SHADER = `
uniform sampler2D colorTexture;
uniform float scanlineIntensity;
in vec2 v_textureCoordinates;

void main() {
  vec2 uv = v_textureCoordinates;
  vec4 color = texture(colorTexture, uv);

  // Scanlines: darken every other pair of rows
  float sl = mod(gl_FragCoord.y, 4.0) < 2.0 ? 1.0 : (1.0 - scanlineIntensity * 0.55);
  color.rgb *= sl;

  // Vignette
  vec2 vc = uv - 0.5;
  color.rgb *= max(0.0, 1.0 - dot(vc, vc) * 2.4);

  // Phosphor green tint
  color.r *= 0.88;
  color.b *= 0.80;

  out_FragColor = clamp(color, 0.0, 1.0);
}
`;

export const THERMAL_SHADER = `
uniform sampler2D colorTexture;
in vec2 v_textureCoordinates;

void main() {
  vec4 col = texture(colorTexture, v_textureCoordinates);
  float t = clamp(dot(col.rgb, vec3(0.299, 0.587, 0.114)), 0.0, 1.0);

  // FLIR-style: cold=blue, mid=green/yellow, hot=red/white
  float r = clamp(t * 2.5 - 0.5, 0.0, 1.0);
  float g = clamp(min(t * 2.5, (1.0 - t) * 2.5), 0.0, 1.0);
  float b = clamp(1.0 - t * 3.0, 0.0, 1.0);
  // Burn white at the hottest areas
  float hot = clamp((t - 0.85) * 6.0, 0.0, 1.0);
  r = mix(r, 1.0, hot);
  g = mix(g, 1.0, hot);
  b = mix(b, 1.0, hot);

  out_FragColor = vec4(r, g, b, 1.0);
}
`;

export const FLARE_SHADER = `
uniform sampler2D colorTexture;
in vec2 v_textureCoordinates;

void main() {
  vec2 uv = v_textureCoordinates;

  // Chromatic aberration
  float shift = 0.003;
  vec4 color;
  color.r = texture(colorTexture, uv + vec2(shift, 0.0)).r;
  color.g = texture(colorTexture, uv).g;
  color.b = texture(colorTexture, uv - vec2(shift, 0.0)).b;
  color.a = 1.0;

  // Lens vignette
  vec2 center = uv - 0.5;
  float dist = length(center);
  color.rgb *= clamp(1.0 - dist * 1.15, 0.0, 1.0);

  // Streak bright areas
  float lum = dot(color.rgb, vec3(0.299, 0.587, 0.114));
  float streak = clamp(lum - 0.65, 0.0, 1.0) * 2.0;
  color.r = clamp(color.r + streak * 0.5, 0.0, 1.0);
  color.g = clamp(color.g + streak * 0.35, 0.0, 1.0);
  color.b = clamp(color.b + streak * 0.05, 0.0, 1.0);

  out_FragColor = color;
}
`;
