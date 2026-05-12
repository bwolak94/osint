import { useMutation, useQuery } from "@tanstack/react-query";
import { domainIntelApi } from "./api";
import type { HarvestRequest } from "./types";

export const useHarvest = () =>
  useMutation({
    mutationFn: (req: HarvestRequest) => domainIntelApi.harvest(req),
  });

export const useAvailableSources = () =>
  useQuery({
    queryKey: ["domain-intel", "sources"],
    queryFn: domainIntelApi.listSources,
    staleTime: Infinity,
  });
