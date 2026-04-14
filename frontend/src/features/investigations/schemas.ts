import { z } from "zod";

export const createInvestigationSchema = z.object({
  title: z
    .string()
    .min(1, "Title is required")
    .max(200, "Title must be at most 200 characters"),
  description: z
    .string()
    .max(2000, "Description must be at most 2000 characters")
    .optional()
    .default(""),
});

export type CreateInvestigationFormData = z.infer<
  typeof createInvestigationSchema
>;
