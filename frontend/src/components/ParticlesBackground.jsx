import { useEffect, useRef } from 'react'

export default function ParticlesBackground({ isDark }) {
  const canvasRef = useRef(null)
  const mouseRef = useRef({ x: null, y: null, click: false })
  const particlesRef = useRef([])
  const rafRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const setSize = () => {
      const dpr = window.devicePixelRatio || 1
      canvas.width = window.innerWidth * dpr
      canvas.height = window.innerHeight * dpr
      canvas.style.width = `${window.innerWidth}px`
      canvas.style.height = `${window.innerHeight}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const createParticles = () => {
      const area = window.innerWidth * window.innerHeight
      const isMobile = window.innerWidth < 768
      const density = isMobile ? 0.0001 : 0.00016
      const maxCount = isMobile ? 70 : 180
      const count = Math.max(40, Math.min(maxCount, Math.floor(area * density)))
      particlesRef.current = Array.from({ length: count }, () => ({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        radius: Math.random() * 1.5 + 0.8,
      }))
    }

    const handleMouseMove = (e) => {
      mouseRef.current = { ...mouseRef.current, x: e.clientX, y: e.clientY }
    }

    const handleMouseLeave = () => {
      mouseRef.current = { ...mouseRef.current, x: null, y: null }
    }

    const handleClick = (e) => {
      mouseRef.current = { ...mouseRef.current, x: e.clientX, y: e.clientY, click: true }
      setTimeout(() => {
        mouseRef.current = { ...mouseRef.current, click: false }
      }, 150)
    }

    const handleTouchMove = (e) => {
      const touch = e.touches[0]
      if (touch) {
        mouseRef.current = { ...mouseRef.current, x: touch.clientX, y: touch.clientY }
      }
    }

    const handleTouchEnd = () => {
      mouseRef.current = { ...mouseRef.current, x: null, y: null }
    }

    const handleTouchStart = (e) => {
      const touch = e.touches[0]
      if (touch) {
        mouseRef.current = { ...mouseRef.current, x: touch.clientX, y: touch.clientY, click: true }
        setTimeout(() => {
          mouseRef.current = { ...mouseRef.current, click: false }
        }, 150)
      }
    }

    const draw = () => {
      const width = window.innerWidth
      const height = window.innerHeight
      ctx.clearRect(0, 0, width, height)

      const particles = particlesRef.current
      const mouse = mouseRef.current
      const connectionDistance = 130
      const mouseConnectionDistance = 180
      const mouseRadius = 160
      const clickRadius = 220
      const baseColor = isDark ? '74, 222, 128' : '38, 154, 76'

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i]

        // mouse interaction
        if (mouse.x !== null && mouse.y !== null) {
          const dx = p.x - mouse.x
          const dy = p.y - mouse.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          // gentle repulsion
          if (dist < mouseRadius && dist > 0) {
            const force = (mouseRadius - dist) / mouseRadius
            const angle = Math.atan2(dy, dx)
            p.vx += Math.cos(angle) * force * 0.45
            p.vy += Math.sin(angle) * force * 0.45
          }

          // click explosion
          if (mouse.click && dist < clickRadius && dist > 0) {
            const force = (clickRadius - dist) / clickRadius
            const angle = Math.atan2(dy, dx)
            p.vx += Math.cos(angle) * force * 6
            p.vy += Math.sin(angle) * force * 6
          }

          // connect particle to mouse
          if (dist < mouseConnectionDistance) {
            const opacity = (1 - dist / mouseConnectionDistance) * (isDark ? 0.45 : 0.3)
            ctx.beginPath()
            ctx.strokeStyle = `rgba(${baseColor}, ${opacity})`
            ctx.lineWidth = 1
            ctx.moveTo(p.x, p.y)
            ctx.lineTo(mouse.x, mouse.y)
            ctx.stroke()
          }
        }

        // apply velocity with friction
        p.x += p.vx
        p.y += p.vy
        p.vx *= 0.96
        p.vy *= 0.96

        // keep a tiny ambient drift
        if (Math.abs(p.vx) < 0.06) p.vx += (Math.random() - 0.5) * 0.025
        if (Math.abs(p.vy) < 0.06) p.vy += (Math.random() - 0.5) * 0.025

        // wrap around edges
        if (p.x < 0) p.x = width
        if (p.x > width) p.x = 0
        if (p.y < 0) p.y = height
        if (p.y > height) p.y = 0

        // draw particle with glow
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${baseColor}, ${isDark ? 0.8 : 0.55})`
        ctx.shadowColor = `rgba(${baseColor}, 0.6)`
        ctx.shadowBlur = isDark ? 8 : 5
        ctx.fill()
        ctx.shadowBlur = 0

        // connect nearby particles
        for (let j = i + 1; j < particles.length; j++) {
          const other = particles[j]
          const dx = p.x - other.x
          const dy = p.y - other.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < connectionDistance) {
            const opacity = (1 - dist / connectionDistance) * (isDark ? 0.28 : 0.2)
            ctx.beginPath()
            ctx.strokeStyle = `rgba(${baseColor}, ${opacity})`
            ctx.lineWidth = 0.8
            ctx.moveTo(p.x, p.y)
            ctx.lineTo(other.x, other.y)
            ctx.stroke()
          }
        }
      }

      // glowing cursor halo
      if (mouse.x !== null && mouse.y !== null) {
        const gradient = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, 80)
        gradient.addColorStop(0, `rgba(${baseColor}, ${isDark ? 0.2 : 0.12})`)
        gradient.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.beginPath()
        ctx.arc(mouse.x, mouse.y, 80, 0, Math.PI * 2)
        ctx.fillStyle = gradient
        ctx.fill()
      }

      rafRef.current = requestAnimationFrame(draw)
    }

    setSize()
    createParticles()
    window.addEventListener('resize', () => {
      setSize()
      createParticles()
    })
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseleave', handleMouseLeave)
    window.addEventListener('click', handleClick)
    window.addEventListener('touchmove', handleTouchMove, { passive: true })
    window.addEventListener('touchend', handleTouchEnd)
    window.addEventListener('touchstart', handleTouchStart, { passive: true })
    rafRef.current = requestAnimationFrame(draw)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      window.removeEventListener('resize', setSize)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseleave', handleMouseLeave)
      window.removeEventListener('click', handleClick)
      window.removeEventListener('touchmove', handleTouchMove)
      window.removeEventListener('touchend', handleTouchEnd)
      window.removeEventListener('touchstart', handleTouchStart)
    }
  }, [isDark])

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-0"
      style={{ opacity: isDark ? 0.95 : 0.8 }}
    />
  )
}
