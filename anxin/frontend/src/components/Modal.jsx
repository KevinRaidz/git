import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'

export default function Modal({ open, title, children, onClose, actions }) {
  const ref = useRef(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog className="react-dialog" ref={ref} onCancel={event => { event.preventDefault(); onClose() }} onClose={onClose}>
      <div className="dialog-heading">
        <h2>{title}</h2>
        <button className="icon-button" type="button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
      </div>
      <div className="dialog-content">{children}</div>
      {actions && <div className="dialog-actions">{actions}</div>}
    </dialog>
  )
}
