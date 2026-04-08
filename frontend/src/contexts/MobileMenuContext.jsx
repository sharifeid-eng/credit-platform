import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const MobileMenuCtx = createContext({ isOpen: false, toggle: () => {}, close: () => {} })

export function MobileMenuProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false)
  const location = useLocation()

  const toggle = useCallback(() => setIsOpen(v => !v), [])
  const close  = useCallback(() => setIsOpen(false), [])

  // Close sidebar on route change
  useEffect(() => { close() }, [location.pathname, close])

  // Lock body scroll when open
  useEffect(() => {
    document.body.style.overflow = isOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  return (
    <MobileMenuCtx.Provider value={{ isOpen, toggle, close }}>
      {children}
    </MobileMenuCtx.Provider>
  )
}

export function useMobileMenu() {
  return useContext(MobileMenuCtx)
}
