import { useEffect, useMemo, useRef } from "react"
import { useAnimationFrame, useMotionValue, useSpring } from "motion/react"

type RGB = [number, number, number]

export interface ParticleSphereProps {
  className?: string
  shellCount?: number // dots on the surface
  bandCount?: number // dense glowing band at the equator
  haloCount?: number // faint dots outside the sphere
  spinSpeed?: number // radians per second
  tilt?: number // base tilt of the spin axis (radians)
  scale?: number // sphere radius as a fraction of the shorter canvas side
  base?: RGB
  accent?: RGB
}

const LEVELS = 5 // alpha buckets keep drawing fast (20 fills per frame)
const MAX_DPR = 1.5
const GOLDEN = Math.PI * (3 - Math.sqrt(5))
const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) / 1.5
const PALETTE: RGB[] = [
  [255, 249, 232], // warm white
  [255, 213, 112], // golden
  [255, 174, 56], // amber
  [255, 106, 24], // orange
]

export function ParticleSphere({
  className,
  shellCount = 9000,
  bandCount = 2600,
  haloCount = 1400,
  spinSpeed = 0.22,
  tilt = 0.35,
  scale = 0.42,
  base = [255, 249, 232],
  accent = [255, 174, 56],
}: ParticleSphereProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const contextRef = useRef<CanvasRenderingContext2D | null>(null)
  const size = useRef({ w: 0, h: 0, dpr: 1 })
  const angle = useRef(0)
  const staticFrameRendered = useRef(false)

  // Pointer position (-1..1) smoothed by springs
  const px = useMotionValue(0)
  const py = useMotionValue(0)
  const sx = useSpring(px, { stiffness: 60, damping: 18 })
  const sy = useSpring(py, { stiffness: 60, damping: 18 })

  // Particle data in flat typed arrays: x, y, z, size, warmth, brightness, phase
  const data = useMemo(() => {
    const total = shellCount + bandCount + haloCount
    const d = new Float32Array(total * 7)
    let i = 0
    const put = (x: number, y: number, z: number, s: number, w: number, b: number) => {
      d.set([x, y, z, s, w, b, Math.random() * Math.PI * 2], i * 7)
      i++
    }

    for (let k = 0; k < shellCount; k++) {
      const y = 1 - (k / (shellCount - 1)) * 2
      const r = Math.sqrt(1 - y * y)
      put(Math.cos(GOLDEN * k) * r, y, Math.sin(GOLDEN * k) * r, 1, 0.05, 0.75)
    }
    for (let k = 0; k < bandCount; k++) {
      const a = Math.random() * Math.PI * 2
      const y = gauss() * 0.16
      const r = Math.sqrt(1 - y * y) * (0.55 + Math.random() * 0.45)
      put(Math.cos(a) * r, y, Math.sin(a) * r, 1.3, 0.9, 0.95)
    }
    for (let k = 0; k < haloCount; k++) {
      const a = Math.random() * Math.PI * 2
      const y = Math.random() * 2 - 1
      const rr = Math.sqrt(1 - y * y)
      const dist = 1.04 + Math.pow(Math.random(), 2.2) * 0.5
      put(Math.cos(a) * rr * dist, y * dist, Math.sin(a) * rr * dist, 1, 0.5, 0.28)
    }
    return d
  }, [shellCount, bandCount, haloCount])

  // Resize with the container
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const resize = () => {
      const dpr = Math.min((typeof window !== "undefined" && window.devicePixelRatio) || 1, MAX_DPR)
      const w = canvas.clientWidth || 800
      const h = canvas.clientHeight || 600
      if (!w || !h) return
      if (size.current.w === w && size.current.h === h && size.current.dpr === dpr) return
      canvas.width = w * dpr
      canvas.height = h * dpr
      size.current = { w, h, dpr }
      try {
        if (typeof canvas.getContext === "function") {
          contextRef.current = canvas.getContext("2d", { alpha: true })
        }
      } catch {
        contextRef.current = null
      }
      staticFrameRendered.current = false
    }

    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(resize)
      ro.observe(canvas)
      resize()
      return () => ro.disconnect()
    } else if (typeof window !== "undefined") {
      window.addEventListener("resize", resize)
      resize()
      return () => window.removeEventListener("resize", resize)
    }
  }, [])

  // Pointer tracking
  useEffect(() => {
    const move = (e: PointerEvent) => {
      px.set((e.clientX / window.innerWidth - 0.5) * 2)
      py.set((e.clientY / window.innerHeight - 0.5) * 2)
    }
    window.addEventListener("pointermove", move)
    return () => window.removeEventListener("pointermove", move)
  }, [px, py])

  const reduceMotion = useRef(false)
  useEffect(() => {
    if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
      reduceMotion.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    }
  }, [])

  useAnimationFrame((t, delta) => {
    const canvas = canvasRef.current
    const ctx = contextRef.current
    if (!canvas || !ctx) return
    const { w, h, dpr } = size.current
    if (!w || !h) return
    if (reduceMotion.current && staticFrameRendered.current) return

    const time = t / 1000
    if (!reduceMotion.current) {
      angle.current += Math.min(delta, 50) / 1000 * spinSpeed
    }

    const rotY = angle.current + sx.get() * 0.4
    const tlt = tilt + sy.get() * 0.25
    const cosY = Math.cos(rotY), sinY = Math.sin(rotY)
    const cosT = Math.cos(tlt), sinT = Math.sin(tlt)
    const cx = w / 2, cy = h / 2
    const radius = Math.min(w, h) * scale

    const buckets: Path2D[][] = PALETTE.map(() =>
      Array.from({ length: LEVELS }, () => new Path2D())
    )

    for (let i = 0; i < data.length; i += 7) {
      const [ox, oy, oz, s, warmth, bright, phase] = [
        data[i], data[i + 1], data[i + 2], data[i + 3], data[i + 4], data[i + 5], data[i + 6],
      ]

      // spin around Y, then tilt around X
      const x = ox * cosY + oz * sinY
      const z1 = -ox * sinY + oz * cosY
      const y = oy * cosT - z1 * sinT
      const z = oy * sinT + z1 * cosT

      const persp = 1 / (1 - z * 0.25)
      const breathe = 1 + Math.sin(time * 1.5 + phase) * 0.006
      const screenX = cx + x * breathe * radius * persp
      const screenY = cy + y * breathe * radius * persp

      const depth = (z + 1.5) / 3
      const alpha = bright * (0.25 + depth * 0.9) * (0.85 + 0.15 * Math.sin(time * 2 + phase * 3))
      const level = Math.max(0, Math.min(LEVELS - 1, Math.floor(alpha * LEVELS)))
      const warmthAtDepth = warmth * Math.max(0, 1 - Math.abs(y) * 3.2)
      const colorIndex = warmthAtDepth > 0.72 ? 3 : warmthAtDepth > 0.42 ? 2 : depth > 0.62 ? 1 : 0

      const px2 = s * persp
      buckets[colorIndex][level].rect(screenX, screenY, px2, px2)
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, w, h)
    ctx.globalCompositeOperation = "lighter"
    PALETTE.forEach((paletteColor, c) => {
      const col = c === 0 ? base : c === 2 ? accent : paletteColor
      for (let a = 0; a < LEVELS; a++) {
        const alpha = ((a + 1) / LEVELS) * (c === 3 ? 0.72 : 0.9)
        ctx.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},${alpha})`
        ctx.fill(buckets[c][a])
      }
    })
    ctx.globalCompositeOperation = "source-over"
    staticFrameRendered.current = reduceMotion.current
  })

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={className}
      style={{
        display: "block",
        width: "100%",
        height: "100%",
      }}
    />
  )
}
