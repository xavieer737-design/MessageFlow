import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../services/api'
import type { User } from '../types'

export function useAuth() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data: user, isLoading, isError } = useQuery({
    queryKey: ['me'],
    queryFn: authApi.me,
    retry: false,
    staleTime: 60_000,
  })

  const login = useMutation({
    mutationFn: authApi.login,
    onSuccess: (loggedInUser) => {
      queryClient.setQueryData(['me'], loggedInUser)
      navigate('/')
    },
  })

  const register = useMutation({
    mutationFn: authApi.register,
    onSuccess: (registeredUser) => {
      queryClient.setQueryData(['me'], registeredUser)
      navigate('/')
    },
  })

  const logout = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.clear()
      navigate('/login')
    },
  })

  return { user: user as User | undefined, isLoading, isError, login, register, logout }
}
