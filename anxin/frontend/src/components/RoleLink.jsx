import { Link } from 'react-router-dom'
import { useSession } from '../App'
import { roleForPath, signInUrl } from '../auth'

export default function RoleLink({ to, children, ...props }) {
  const { session } = useSession()
  const role = roleForPath(to)
  return <Link to={role === session?.role ? to : signInUrl(role, to)} {...props}>{children}</Link>
}
