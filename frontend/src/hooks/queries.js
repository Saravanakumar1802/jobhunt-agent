/** TanStack Query hooks: server state is cached, deduped and invalidated after mutations. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { profilesApi, statusApi, trackerApi } from "../api/endpoints";

export const keys = {
  profiles: ["profiles"],
  skills: ["skills"],
  tracker: ["tracker"],
  status: ["status"],
  models: ["models"],
};

export const useProfiles = () => useQuery({ queryKey: keys.profiles, queryFn: profilesApi.list });

export const useSkillSuggestions = () =>
  useQuery({ queryKey: keys.skills, queryFn: profilesApi.skillSuggestions, staleTime: Infinity });

export function useSaveProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) => (id ? profilesApi.update(id, body) : profilesApi.create(body)),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.profiles }),
  });
}

export function useDeleteProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: profilesApi.remove,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.profiles }),
  });
}

export const useTracker = () => useQuery({ queryKey: keys.tracker, queryFn: trackerApi.list });

export function useTrackJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ body, profileHash }) => trackerApi.track(body, profileHash),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.tracker }),
  });
}

export function useUpdateTracked() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, ...body }) => trackerApi.update(jobId, body),
    // Optimistic status change so the board feels instant.
    onMutate: async ({ jobId, ...body }) => {
      await qc.cancelQueries({ queryKey: keys.tracker });
      const prev = qc.getQueryData(keys.tracker);
      qc.setQueryData(keys.tracker, (list = []) => list.map((t) => (t.job_id === jobId ? { ...t, ...body } : t)));
      return { prev };
    },
    onError: (_e, _v, ctx) => qc.setQueryData(keys.tracker, ctx.prev),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.tracker }),
  });
}

export function useUntrack() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: trackerApi.remove,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.tracker }),
  });
}

export const useStatus = () => useQuery({ queryKey: keys.status, queryFn: statusApi.status, refetchInterval: 60_000 });

export const useModels = () => useQuery({ queryKey: keys.models, queryFn: statusApi.models, refetchInterval: 120_000 });

export function useModelsMutation(fn) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: (data) => qc.setQueryData(keys.models, (old) => ({ ...old, ...data })) });
}
