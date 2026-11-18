import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Category, Region, Unit } from "./types";

const STATIC = { staleTime: 5 * 60_000 };

export const useRegions = () => useQuery({ queryKey: ["regions"], queryFn: () => api.get<Region[]>("/regions"), ...STATIC });
export const useUnits = () => useQuery({ queryKey: ["units"], queryFn: () => api.get<Unit[]>("/units"), ...STATIC });
export const useCategories = (withAttributes = false) =>
  useQuery({ queryKey: ["categories", withAttributes], queryFn: () => api.get<Category[]>("/categories", { with_attributes: withAttributes }), ...STATIC });
export const useCategory = (id: number | null | undefined) =>
  useQuery({ queryKey: ["category", id], queryFn: () => api.get<Category>(`/categories/${id}`), enabled: !!id, ...STATIC });
