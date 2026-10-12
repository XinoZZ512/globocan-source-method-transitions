suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(patchwork)
  library(scales)
  library(MASS)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript generate_figures_ijc.R <project>")
project <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

tables_v2 <- file.path(project, "results", "tables_v2")
models_v2 <- file.path(project, "results", "models_v2")
normalized <- file.path(project, "data", "normalized")
adjudication <- file.path(project, "data", "adjudication")
figures <- file.path(project, "results", "figures")
dir.create(tables_v2, recursive = TRUE, showWarnings = FALSE)
dir.create(figures, recursive = TRUE, showWarnings = FALSE)

# The visual grammar follows the public IJC benchmark implementation:
# white background, compact base-graphics proportions, restrained axes,
# deep registry colours, LOWESS, open-square summaries, and YlOrBr tiles.
# Reference: drmehmetzafer/globocan-cross-cycle, commit
# 8061612d87eb7c4a9d845ff624a03f0490dd8c16.
ink <- "#111111"
grid <- "#D9DEE2"
muted <- "#667078"
red <- "#8A1C22"
rust <- "#8A4B0F"
teal <- "#0B6B5E"
blue <- "#1F4E79"
light_na <- "#ECECEC"

read_csv_clean <- function(path) {
  lines <- readLines(path, encoding = "UTF-8", warn = FALSE)
  if (!length(lines)) stop("Empty CSV: ", path)
  bom <- intToUtf8(0xFEFF)
  lines[[1L]] <- sub(paste0("^", bom), "", lines[[1L]])
  x <- read.csv(text = paste(lines, collapse = "\n"), stringsAsFactors = FALSE, check.names = FALSE)
  names(x) <- sub(paste0("^", bom), "", names(x))
  x
}

save_plot <- function(plot, stem, width, height) {
  ggsave(file.path(figures, paste0(stem, ".png")), plot, width = width, height = height, units = "in", dpi = 400, bg = "white")
  ggsave(file.path(figures, paste0(stem, ".pdf")), plot, width = width, height = height, units = "in", device = grDevices::cairo_pdf, bg = "white")
  ggsave(file.path(figures, paste0(stem, ".tiff")), plot, width = width, height = height, units = "in", dpi = 600, device = "tiff", compression = "lzw", bg = "white")
}

theme_ijc <- function(base_size = 9) {
  theme_classic(base_size = base_size, base_family = "Arial") +
    theme(
      plot.title = element_text(face = "bold", size = base_size + 1, colour = ink, hjust = 0),
      plot.subtitle = element_text(size = base_size - 0.5, colour = muted, hjust = 0),
      plot.caption = element_text(size = base_size - 1, colour = muted, hjust = 0.5),
      axis.title = element_text(colour = ink),
      axis.text = element_text(colour = ink),
      axis.line = element_line(colour = ink, linewidth = 0.4),
      axis.ticks = element_line(colour = ink, linewidth = 0.35),
      panel.grid.major = element_line(colour = grid, linewidth = 0.28),
      panel.grid.minor = element_blank(),
      legend.title = element_blank(),
      legend.text = element_text(colour = ink, size = base_size - 1),
      legend.key = element_blank(),
      strip.background = element_blank(),
      strip.text = element_text(face = "bold", colour = ink, size = base_size),
      plot.margin = margin(6, 8, 6, 8)
    )
}

tile_scale <- function() {
  scale_fill_gradientn(
    colours = hcl.colors(20, "YlOrBr", rev = TRUE),
    limits = c(0, 60), breaks = c(0, 10, 20, 30, 40, 50, 60),
    oob = scales::squish, na.value = light_na, name = "Percentage"
  )
}

archive_old_figures <- function() {
  archive <- file.path(figures, "SUPERSEDED_PRE_IJC_REDESIGN")
  dir.create(archive, recursive = TRUE, showWarnings = FALSE)
  old <- list.files(figures, pattern = "^Figure_.*\\.(png|pdf|tiff)$", full.names = TRUE)
  if (length(old)) file.rename(old, file.path(archive, basename(old)))
  writeLines(c(
    "These files are superseded by the IJC-reference redesign.",
    "They are retained only for audit history and are excluded from active packaging."
  ), file.path(archive, "README.txt"))
}

archive_old_figures()

final <- read_csv_clean(file.path(adjudication, "adjudication_template_round3_FINAL_RESTRICTED.csv"))
key <- read_csv_clean(file.path(adjudication, "blind_key_RESTRICTED.csv"))
cells <- read_csv_clean(file.path(normalized, "paired_cells.csv"))
effects <- read_csv_clean(file.path(models_v2, "primary_model_v2.csv"))
country <- read_csv_clean(file.path(tables_v2, "country_level_v2.csv"))

stopifnot(nrow(final) == 370L, nrow(key) == 370L, nrow(cells) == 20350L)
if (!all(c("blind_id", "indicator", "adjudicated_classification") %in% names(final))) stop("Final adjudication fields missing")
if (!all(c("blind_id", "iso3") %in% names(key))) stop("Restricted key fields missing")

exposure <- final %>%
  inner_join(key %>% dplyr::select(blind_id, iso3), by = "blind_id", relationship = "one-to-one") %>%
  dplyr::select(iso3, indicator, adjudicated_classification)

category_levels <- c("ADMINISTRATIVE_OR_WORDING_ONLY", "SUBSTANTIVE_SAME_DIRECTNESS", "TOWARD_MORE_DIRECT", "TOWARD_MORE_INDIRECT", "UNCLASSIFIABLE")
category_labels <- c(
  ADMINISTRATIVE_OR_WORDING_ONLY = "Administrative / wording",
  SUBSTANTIVE_SAME_DIRECTNESS = "Substantive, same directness",
  TOWARD_MORE_DIRECT = "Toward more direct",
  TOWARD_MORE_INDIRECT = "Toward more indirect",
  UNCLASSIFIABLE = "Unclassifiable"
)

directness_labels <- c(
  `0` = "0 No direct data / borrowing",
  `1` = "1 Modelled / M:I / scaled",
  `2` = "2 Subnational",
  `3` = "3 National"
)

exposure <- exposure %>%
  mutate(
    substantive_transition = adjudicated_classification %in% c("SUBSTANTIVE_SAME_DIRECTNESS", "TOWARD_MORE_DIRECT", "TOWARD_MORE_INDIRECT"),
    wording_only = adjudicated_classification == "ADMINISTRATIVE_OR_WORDING_ONLY"
  )

# Figure 1A: final human classification composition.
fig1a <- exposure %>%
  count(indicator, adjudicated_classification, name = "n") %>%
  complete(indicator = c("Incidence", "Mortality"), adjudicated_classification = category_levels, fill = list(n = 0)) %>%
  mutate(
    category = factor(unname(category_labels[adjudicated_classification]), levels = unname(category_labels)),
    share = n / 185,
    label = sprintf("%d\n%.1f%%", n, 100 * share)
  )
if (any(abs(fig1a %>% group_by(indicator) %>% summarise(s = sum(share), .groups = "drop") %>% pull(s) - 1) > 1e-10)) stop("Figure 1A shares do not sum to 1")

# Figure 1B/C: coarse official directness movement, shown separately from semantic adjudication.
directness <- cells %>%
  distinct(iso3, indicator, source_directness_score_2022, source_directness_score_2024) %>%
  count(indicator, source_directness_score_2022, source_directness_score_2024, name = "n") %>%
  complete(indicator = c("Incidence", "Mortality"), source_directness_score_2022 = 0:3, source_directness_score_2024 = 0:3, fill = list(n = 0)) %>%
  mutate(share = 100 * n / 185, label = sprintf("%d", n))

fig1a_plot <- ggplot(fig1a, aes(x = category, y = indicator, fill = share)) +
  geom_tile(colour = "white", linewidth = 0.5) +
  geom_text(aes(label = label), size = 2.55, lineheight = 0.9, fontface = "bold") +
  scale_x_discrete(labels = c("Administrative /\nwording", "Substantive /\nsame directness", "More\ndirect", "More\nindirect", "Unclassifiable")) +
  scale_y_discrete(limits = c("Mortality", "Incidence")) +
  scale_fill_gradientn(colours = hcl.colors(20, "YlOrBr", rev = TRUE), limits = c(0, 0.75), breaks = c(0, .25, .5, .75), labels = percent_format(accuracy = 1), name = "Share") +
  labs(x = NULL, y = NULL, subtitle = "(A) Final human-adjudicated category") +
  theme_ijc(8) + theme(axis.text.x = element_text(angle = 0, vjust = 0.5), panel.grid = element_blank(), legend.position = "right")

make_directness_plot <- function(indicator, panel_label) {
  d <- directness %>% filter(indicator == !!indicator) %>%
    mutate(
      from = factor(source_directness_score_2022, levels = 3:0, labels = c("3 National", "2 Subnational", "1 Modelled /\nM:I / scaled", "0 No direct /\nborrowing")),
      to = factor(source_directness_score_2024, levels = 0:3, labels = c("0 No direct /\nborrowing", "1 Modelled /\nM:I / scaled", "2 Subnational", "3 National"))
    )
  ggplot(d, aes(x = to, y = from, fill = share)) +
    geom_tile(colour = "white", linewidth = 0.5) +
    geom_text(aes(label = label), size = 2.7, fontface = "bold") +
    tile_scale() +
    labs(x = "2024 directness level", y = "2022 directness level", subtitle = paste0(panel_label, " ", indicator)) +
    theme_ijc(7.5) +
    theme(axis.text.x = element_text(angle = 0, hjust = 0.5, vjust = 0.5, lineheight = 0.9), axis.text.y = element_text(size = 6.5, lineheight = 0.9), panel.grid = element_blank(), legend.position = "right")
}
fig1 <- fig1a_plot + make_directness_plot("Incidence", "(B)") + make_directness_plot("Mortality", "(C)") + plot_layout(widths = c(1.25, 1, 1))
save_plot(fig1, "Figure_1_source_method_transitions", 13.6, 5.4)
write.csv(fig1a, file.path(tables_v2, "figure1_adjudicated_category_heatmap.csv"), row.names = FALSE)
write.csv(directness, file.path(tables_v2, "figure1_directness_transition_matrices.csv"), row.names = FALSE)

# Figure 2: IJC-style country scatter, LOWESS, and open-square group medians.
model_effects <- effects %>% mutate(indicator = factor(indicator, levels = c("Incidence", "Mortality")))
fig2_data <- country %>%
  filter(indicator %in% c("Incidence", "Mortality"), !is.na(substantive_transition), !is.na(hdi_z)) %>%
  mutate(
    transition = ifelse(substantive_transition, "Substantive transition", "No substantive transition"),
    transition = factor(transition, levels = c("No substantive transition", "Substantive transition"))
  )
if (!identical(as.integer(table(fig2_data$indicator)), c(175L, 176L))) stop("Figure 2 analytic sample size mismatch")

make_scatter <- function(indicator, panel_label) {
  d <- fig2_data %>% filter(indicator == !!indicator)
  e <- model_effects %>% filter(indicator == !!indicator)
  ann <- sprintf("Adjusted difference %+.2f pp\n95%% CI %+.2f to %+.2f\nPermutation P = %.3f", e$adjusted_marginal_difference_pp, e$bootstrap_ci_low, e$bootstrap_ci_high, e$permutation_p)
  med <- d %>% group_by(transition) %>% summarise(x = median(median_asr_2022), y = median(median_aspd), .groups = "drop")
  smooth <- d %>% group_by(transition) %>% group_modify(~ {
    if (nrow(.x) < 6L) return(tibble())
    fit <- stats::lowess(.x$median_asr_2022, .x$median_aspd, f = 0.6, iter = 3)
    support <- quantile(.x$median_asr_2022, probs = c(0.05, 0.95), na.rm = TRUE, names = FALSE)
    tibble(median_asr_2022 = fit$x, median_aspd = fit$y) %>%
      filter(median_asr_2022 >= support[[1]], median_asr_2022 <= support[[2]])
  }) %>% ungroup()
  ggplot(d, aes(x = median_asr_2022, y = median_aspd, colour = transition)) +
    geom_point(alpha = 0.38, size = 1.45) +
    geom_line(data = smooth, aes(x = median_asr_2022, y = median_aspd, group = transition, colour = transition), linewidth = 0.8, inherit.aes = FALSE) +
    geom_point(data = med, aes(x = x, y = y), inherit.aes = FALSE, shape = 0, colour = ink, size = 4, stroke = 1.0) +
    annotate("label", x = -Inf, y = Inf, label = ann, hjust = -0.04, vjust = 1.12, size = 2.65, fill = "white", colour = ink, lineheight = 1.05) +
    scale_colour_manual(values = c("No substantive transition" = blue, "Substantive transition" = rust), name = NULL) +
    scale_x_continuous(expand = expansion(mult = c(0.04, 0.04))) +
    scale_y_continuous(limits = c(0, 130), breaks = seq(0, 120, 20), expand = c(0, 0)) +
    labs(x = "Baseline median ASR, 2022 (per 100 000)", y = "Country median ASPD (%)", subtitle = paste0(panel_label, " ", indicator)) +
    theme_ijc(8.5) + theme(legend.position = "top", legend.key.width = unit(0.8, "lines"))
}
fig2 <- make_scatter("Incidence", "(A)") + make_scatter("Mortality", "(B)") + plot_layout(ncol = 2, guides = "collect") & theme(legend.position = "top")
save_plot(fig2, "Figure_2_country_revision_scatter", 13.0, 5.2)
write.csv(fig2_data, file.path(tables_v2, "figure2_country_revision_scatter_data.csv"), row.names = FALSE)
write.csv(model_effects, file.path(tables_v2, "figure2_adjusted_effects.csv"), row.names = FALSE)

# Figure 3: 32-cancer heatmap in the exact compact numerical style of the reference.
heat <- cells %>%
  inner_join(exposure %>% dplyr::select(iso3, indicator, substantive_transition, wording_only), by = c("iso3", "indicator"), relationship = "many-to-one") %>%
  filter(asr_2022 > 0.5, wording_only | substantive_transition) %>%
  mutate(group = ifelse(substantive_transition, "Substantive transition", "Administrative / wording-only")) %>%
  group_by(indicator, cancer_code, cancer_label, group) %>%
  summarise(median_aspd = median(aspd, na.rm = TRUE), n = sum(!is.na(aspd)), .groups = "drop")
 cancers <- cells %>% distinct(cancer_code, cancer_label) %>%
  left_join(cells %>% filter(asr_2022 > 0.5) %>% group_by(cancer_code) %>% summarise(overall = median(aspd, na.rm = TRUE), .groups = "drop"), by = "cancer_code") %>%
  arrange(desc(overall), cancer_code)
heat <- heat %>% complete(indicator = c("Incidence", "Mortality"), cancer_code = cancers$cancer_code, group = c("Administrative / wording-only", "Substantive transition")) %>%
  left_join(cancers %>% transmute(cancer_code, cancer_name = cancer_label), by = "cancer_code") %>%
  mutate(indicator = factor(indicator, levels = c("Incidence", "Mortality")), group = factor(group, levels = c("Administrative / wording-only", "Substantive transition")), cancer_name = factor(cancer_name, levels = rev(cancers$cancer_label)), label = ifelse(is.na(median_aspd), "NA", ifelse(median_aspd >= 60, ">=60", sprintf("%.0f", median_aspd))))
if (nrow(heat) != 128L || sum(!is.na(heat$median_aspd)) != 127L) stop("Figure 3 must have 128 cells and 127 numeric values")
write.csv(heat, file.path(tables_v2, "figure3_cancer_heatmap_data.csv"), row.names = FALSE)
heat <- heat %>% mutate(indicator = factor(indicator, levels = c("Incidence", "Mortality"), labels = c("(A) Incidence", "(B) Mortality")))
fig3 <- ggplot(heat, aes(x = group, y = cancer_name, fill = median_aspd)) +
  geom_tile(colour = "white", linewidth = 0.45) +
  geom_text(aes(label = label, colour = ifelse(is.na(median_aspd) | median_aspd < 30, "dark", "light")), size = 2.45, fontface = "bold") +
  scale_colour_manual(values = c(dark = ink, light = "white"), guide = "none") +
  tile_scale() +
  facet_grid(. ~ indicator, scales = "free_x", space = "free_x") +
  labs(x = NULL, y = NULL, caption = "Colours are saturated at 60%; exact values are printed in the cells. NA denotes a structural absence, not zero.") +
  theme_ijc(8) + theme(axis.text.x = element_text(size = 7.3), axis.text.y = element_text(size = 7.2), panel.grid = element_blank(), legend.position = "right", panel.spacing.x = unit(1.0, "lines"))
save_plot(fig3, "Figure_3_cancer_heterogeneity", 11.8, 12.4)

# Figure 4: external convergent checks, retaining the article's point/square/LOWESS grammar.
pbcr <- read_csv_clean(file.path(tables_v2, "figure4_pbcr_plot_data.csv")) %>% filter(indicator == "Incidence")
cod <- read_csv_clean(file.path(tables_v2, "figure4_cod_completeness_plot_data.csv"))
pbcr$status <- factor(pbcr$pbcr_status, levels = c("No", "Yes"))
set.seed(20261011)
pbcr$x <- as.numeric(pbcr$status) + runif(nrow(pbcr), -0.045, 0.045)
pbcr_med <- pbcr %>% group_by(status) %>% summarise(x = as.numeric(first(status)), y = median(median_aspd, na.rm = TRUE), .groups = "drop")
pbcr_diff <- median(pbcr$median_aspd[pbcr$status == "Yes"], na.rm = TRUE) - median(pbcr$median_aspd[pbcr$status == "No"], na.rm = TRUE)
fig4a <- ggplot(pbcr, aes(x = x, y = median_aspd, colour = status)) +
  geom_point(alpha = 0.42, size = 1.45) +
  geom_point(data = pbcr_med, aes(x = x, y = y), inherit.aes = FALSE, shape = 0, colour = ink, size = 4, stroke = 1.0) +
  annotate("label", x = 1.02, y = Inf, label = sprintf("Median difference\nYes - No = %+.2f pp\nn = %d", pbcr_diff, nrow(pbcr)), hjust = 0, vjust = 1.12, size = 2.65, fill = "white", colour = ink) +
  scale_x_continuous(breaks = 1:2, labels = c("No", "Yes"), limits = c(0.65, 2.35)) +
  scale_colour_manual(values = c(No = red, Yes = teal), guide = "none") +
  labs(x = "Population-based cancer registry existence, 2021", y = "Country median ASPD (%)", subtitle = "(A) Incidence") +
  theme_ijc(8.2) + theme(panel.grid.major.x = element_blank())

rho <- cor(cod$cod_completeness_value, cod$median_aspd, method = "spearman", use = "complete.obs")
cod <- cod %>% filter(!is.na(cod_completeness_value), !is.na(median_aspd))
cod_smooth_fit <- stats::lowess(cod$cod_completeness_value, cod$median_aspd, f = 0.6, iter = 3)
cod_support <- quantile(cod$cod_completeness_value, probs = c(0.05, 0.95), na.rm = TRUE, names = FALSE)
cod_smooth <- data.frame(
  cod_completeness_value = cod_smooth_fit$x,
  median_aspd = cod_smooth_fit$y
) %>% filter(cod_completeness_value >= cod_support[[1]], cod_completeness_value <= cod_support[[2]])
qs <- quantile(cod$cod_completeness_value, probs = seq(0, 1, .25), na.rm = TRUE)
cod$quartile <- cut(cod$cod_completeness_value, breaks = unique(qs), include.lowest = TRUE)
cod_med <- cod %>% group_by(quartile) %>% summarise(x = median(cod_completeness_value), y = median(median_aspd), .groups = "drop")
fig4b <- ggplot(cod, aes(x = cod_completeness_value, y = median_aspd)) +
  geom_point(colour = teal, alpha = 0.38, size = 1.45) +
  geom_line(data = cod_smooth, aes(x = cod_completeness_value, y = median_aspd), inherit.aes = FALSE, colour = ink, linewidth = 0.85) +
  geom_point(data = cod_med, aes(x = x, y = y), inherit.aes = FALSE, shape = 0, colour = ink, size = 4, stroke = 1.0) +
  annotate("label", x = -Inf, y = Inf, label = sprintf("Spearman rho = %+.2f\nn = %d", rho, nrow(cod)), hjust = -0.04, vjust = 1.12, size = 2.65, fill = "white", colour = ink) +
  scale_y_continuous(limits = c(0, 130), breaks = seq(0, 120, 20), expand = c(0, 0)) +
  labs(x = "WHO cause-of-death completeness (%)", y = "Country median ASPD (%)", subtitle = "(B) Mortality") +
  theme_ijc(8.2)
fig4 <- fig4a + fig4b + plot_layout(widths = c(0.9, 1.1))
save_plot(fig4, "Figure_4_external_convergence", 13.0, 5.2)
write.csv(pbcr, file.path(tables_v2, "figure4_pbcr_plot_data.csv"), row.names = FALSE)
write.csv(cod, file.path(tables_v2, "figure4_cod_completeness_plot_data.csv"), row.names = FALSE)
writeLines(c(
  "Figure 2 and Figure 4 smoothers follow the pinned IJC reference grammar.",
  "lowess_f=0.6; lowess_iter=3; smoother lines are restricted to the group-specific 5th-95th percentile of the observed x range.",
  "All observed points and group medians are retained; smoothers are descriptive and are not used for inference."
), file.path(tables_v2, "lowess_source_manifest.txt"))

# Supplementary Figure S1: exact Bland-Altman benchmark grammar from the reference article.
make_ba <- function(indicator, panel_label) {
  d <- cells %>% filter(indicator == !!indicator, asr_2022 > 0.1) %>% mutate(mean_asr = (asr_2022 + asr_2024) / 2, difference = asr_2024 - asr_2022)
  bias <- mean(d$difference, na.rm = TRUE); sdv <- sd(d$difference, na.rm = TRUE)
  lo <- bias - 1.96 * sdv; hi <- bias + 1.96 * sdv
  ggplot(d, aes(x = mean_asr, y = difference)) +
    geom_point(colour = teal, alpha = 0.23, size = 0.65) +
    geom_hline(yintercept = bias, colour = rust, linewidth = 0.8) +
    geom_hline(yintercept = c(lo, hi), colour = rust, linetype = "dashed", linewidth = 0.55) +
    geom_hline(yintercept = 0, colour = "grey70", linewidth = 0.35) +
    annotate("label", x = Inf, y = -Inf, label = sprintf("mean diff %+.2f\n95%% LoA [%+.2f, %+.2f]", bias, lo, hi), hjust = 1.04, vjust = -0.12, size = 2.55, fill = "white", colour = ink) +
    scale_x_continuous(trans = "log10", breaks = c(1, 10, 100), labels = c("1", "10", "100")) +
    labs(x = "Mean ASR of the two releases, per 100 000", y = "Difference (2024 - 2022), per 100 000", subtitle = paste0(panel_label, " ", indicator)) +
    theme_ijc(8.2)
}
fig_s1 <- make_ba("Incidence", "(A)") + make_ba("Mortality", "(B)") + plot_layout(ncol = 2)
save_plot(fig_s1, "Supplementary_Figure_S1_bland_altman", 13.0, 5.0)

cat("IJC-reference figure redesign completed.\n")
