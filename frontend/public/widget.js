/*
 * Professor Pepe website widget.
 *
 * Drop one script tag into any page and the Pepecoin community assistant
 * appears as a floating chat button, or fills a container of your choice:
 *
 *   <script src="https://professor-pepe-agent.onrender.com/widget.js"></script>
 *
 * Options, as data- attributes on the script tag (all optional):
 *   data-mode="floating" | "inline"   floating button (default) or inside a container
 *   data-target="#professor-pepe"     inline only: CSS selector of the container
 *   data-position="right" | "left"    floating only: which corner
 *   data-color="#269a4c"              launcher button colour
 *   data-open="true"                  floating only: start opened
 *   data-height="600"                 inline only: height in px (default 600)
 *   data-pulse="false"                floating only: turn off the attention pulse
 *   data-teaser="Questions? Ask me."  floating only: short label next to the
 *                                     button until the chat is opened once
 *
 * The app runs inside an iframe served from the Professor Pepe origin, so
 * nothing here touches your page's styles or scripts, and nothing of your
 * page is visible to the chat. window.ProfessorPepe.open() / .close() /
 * .toggle() are available for your own buttons.
 */
(function () {
  if (window.ProfessorPepe) return

  var script = document.currentScript
  if (!script) return
  var origin = new URL(script.src, window.location.href).origin
  var data = script.dataset || {}
  var mode = data.mode === 'inline' ? 'inline' : 'floating'
  var side = data.position === 'left' ? 'left' : 'right'
  var color = data.color || '#269a4c'
  var pulse = data.pulse !== 'false'
  var teaserText = data.teaser || ''
  var appUrl = origin + '/?embed=1'
  var logo = origin + '/logo.png'

  function makeFrame() {
    var frame = document.createElement('iframe')
    frame.src = appUrl
    frame.title = 'Professor Pepe'
    frame.setAttribute('allow', 'clipboard-write')
    frame.setAttribute('loading', 'lazy')
    frame.className = 'pp-widget-frame'
    return frame
  }

  // The CSS is a stylesheet from this origin, not an inline <style>: a host
  // page with a strict Content-Security-Policy can allow one origin, but
  // would have to allow 'unsafe-inline' for injected styles. Corner and
  // colour travel as a class and a custom property, which CSP does not
  // police (they are set through the CSSOM, not through style attributes).
  var link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = origin + '/widget.css'
  document.head.appendChild(link)

  // ---- inline: the app fills a container on the page ----------------------
  if (mode === 'inline') {
    var target = document.querySelector(data.target || '#professor-pepe')
    if (!target) {
      target = document.createElement('div')
      script.parentNode.insertBefore(target, script)
    }
    var height = parseInt(data.height, 10) || 600
    target.classList.add('pp-widget-inline')
    target.style.height = height + 'px'
    target.appendChild(makeFrame())
    window.ProfessorPepe = { mode: 'inline', open: function () {}, close: function () {}, toggle: function () {} }
    return
  }

  // ---- floating: a launcher button and a panel ---------------------------
  var panel = document.createElement('div')
  panel.className = 'pp-widget-panel pp-' + side
  panel.setAttribute('role', 'dialog')
  panel.setAttribute('aria-label', 'Professor Pepe chat')

  var launcher = document.createElement('button')
  launcher.type = 'button'
  launcher.className = 'pp-widget-launcher pp-' + side + (pulse ? ' pp-pulse' : '')
  launcher.style.setProperty('--pp-color', color)
  launcher.setAttribute('aria-label', 'Chat with Professor Pepe')
  launcher.setAttribute('aria-expanded', 'false')
  launcher.innerHTML =
    '<img src="' + logo + '" alt="">' +
    '<svg class="pp-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>'

  var teaser = null
  if (teaserText) {
    teaser = document.createElement('button')
    teaser.type = 'button'
    teaser.className = 'pp-widget-teaser pp-' + side
    teaser.textContent = teaserText
    teaser.addEventListener('click', function () { open() })
  }

  var isOpen = false
  var loaded = false

  function open() {
    // One open is enough: the visitor knows the chat is there now.
    launcher.classList.remove('pp-pulse')
    if (teaser) { teaser.classList.remove('pp-show'); teaser.style.display = 'none' }
    if (!loaded) {
      // The app is only fetched when someone actually opens it: a page that
      // embeds the widget should not pay for the chat on every visit.
      panel.appendChild(makeFrame())
      loaded = true
    }
    isOpen = true
    panel.classList.add('pp-open')
    launcher.classList.add('pp-open')
    launcher.setAttribute('aria-expanded', 'true')
    launcher.setAttribute('aria-label', 'Close Professor Pepe')
  }
  function close() {
    isOpen = false
    panel.classList.remove('pp-open')
    launcher.classList.remove('pp-open')
    launcher.setAttribute('aria-expanded', 'false')
    launcher.setAttribute('aria-label', 'Chat with Professor Pepe')
  }
  function toggle() { isOpen ? close() : open() }

  launcher.addEventListener('click', toggle)
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen) close()
  })

  function mount() {
    document.body.appendChild(panel)
    document.body.appendChild(launcher)
    if (teaser) {
      document.body.appendChild(teaser)
      // Appears after the page has settled, not in the same instant as the
      // button, so it reads as someone speaking up rather than as page chrome.
      setTimeout(function () { if (!isOpen) teaser.classList.add('pp-show') }, 2500)
    }
    if (data.open === 'true') open()
  }
  if (document.body) mount()
  else document.addEventListener('DOMContentLoaded', mount)

  window.ProfessorPepe = { mode: 'floating', open: open, close: close, toggle: toggle }
})()
