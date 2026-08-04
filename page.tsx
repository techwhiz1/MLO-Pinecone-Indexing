'use client';

import {
  useCallback,
  ChangeEvent,
  Dispatch,
  FormEvent,
  JSX,
  ReactNode,
  SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { ImagePlus, Loader2, Plus, Search, Trash2, Upload, X } from 'lucide-react';
import { enqueueSnackbar } from 'notistack';
import MediaModal, { SelectedMediaFile } from '@/components/ui/modals/MediaModal';
import {
  ApiMicrosite,
  ApiProductCategory,
  fetchProductCategories,
  fetchSupplierMicrosite,
} from '@/services/productCategories';
import {
  createProduct,
  fetchPublicProductTaxonomy,
  type CreateProductPayload,
  type ProductRepresentativeDayKey,
  type PublicProductTaxonomyTreeItem,
} from '@/services/products';
import { MediaResource, replaceMedia, uploadMany } from '@/services/media';
import {
  applyRepresentativeAvailabilityChange,
  type RepresentativeAvailabilityState,
} from '@/lib/utils/representativeAvailability';
import {
  buildRepresentativesPayloadForApi,
  createEmptyProductRepFormRow,
  MAX_PRODUCT_REPRESENTATIVES,
  validateProductRepFormRows,
  type ProductRepFormRow,
} from '@/lib/utils/productRepresentatives';

type CategoryNode = ApiProductCategory & { children: ApiProductCategory[] };
type MediaSelection = { id?: string; url: string };
type ScrapedTaxonomyNode = {
  id?: string | null;
  name?: string | null;
  slug?: string | null;
};
type RawScrapedFacet = {
  facet_id?: string | null;
  value?: string | number | boolean | null;
  value_type?: string | null;
  key?: string | null;
  label?: string | null;
  sort_order?: number | null;
};

type RawScrapedProduct = {
  title?: string | null;
  short_description?: string | null;
  shortDescription?: string | null;
  summary?: string | null;
  description?: string | null;
  image_url?: string | Array<string | null> | null;
  image_urls?: Array<string | null> | null;
  video_url?: string | Array<string | null> | null;
  video_urls?: Array<string | null> | null;
  gallery_images?: Array<string | null> | null;
  images?: Array<string | null> | null;
  doc_url?: string | null;
  document_urls?: Array<string | null> | null;
  cluster?: ScrapedTaxonomyNode | string | null;
  super_category?: ScrapedTaxonomyNode | string | null;
  category?: ScrapedTaxonomyNode | string | null;
  class?: ScrapedTaxonomyNode | string | null;
  class_name?: ScrapedTaxonomyNode | string | null;
  sub_class?: ScrapedTaxonomyNode | string | null;
  sub_class_name?: ScrapedTaxonomyNode | string | null;
  subcategory?: ScrapedTaxonomyNode | string | null;
  facets?: RawScrapedFacet[] | null;
  attributes?: Record<string, string | null> | null;
  product_url?: string | null;
};

type ScrapedProduct = {
  title: string;
  shortDescription: string;
  description: string;
  imageUrl: string | null;
  imageUrls: string[];
  videoUrls: string[];
  docUrl: string | null;
  documentUrls: string[];
  category: string | null;
  subcategory: string | null;
  superCategoryId: string | null;
  taxonomyCategoryId: string | null;
  taxonomyClassId: string | null;
  taxonomySubClassId: string | null;
  sourceTaxonomy: {
    superCategory: ScrapedTaxonomyNode | null;
    category: ScrapedTaxonomyNode | null;
    className: ScrapedTaxonomyNode | null;
    subClass: ScrapedTaxonomyNode | null;
  };
  facets: RawScrapedFacet[];
  facetValues: Record<string, string | string[] | number | boolean>;
  attributes: Record<string, string | null>;
  productUrl: string | null;
};

type SourceEnrichmentPayload = {
  title: string | null;
  description: string | null;
  images: string[];
  features: string[];
  application: string | null;
  specifications: Array<{ label: string; value: string }>;
};

type ScrapeProductsResponse = {
  product?: RawScrapedProduct | null;
  products?: RawScrapedProduct[];
  total_products?: number;
  source_url?: string | null;
};

type FacetValueRecord = Record<string, string | string[] | number | boolean>;

const CURRENCY_OPTIONS = ['USD', 'EUR', 'GBP'] as const;
const MAX_GALLERY_IMAGES = 6;
const DEFAULT_SCRAPE_URL = '';

const CANONICAL_OPTION_FACETS = {
  condition: {
    key: 'new-remanufactured-refurbished',
    options: ['New', 'Refurbished'],
  },
  oemAftermarket: {
    key: 'oem-aftermarket-third-party',
    options: ['OEM Original', 'Aftermarket'],
  },
  serviceRegion: {
    key: 'service-support-region',
    options: ['Global', 'American', 'EMEA', 'Africa', 'Asia-Pacific'],
  },
} as const;

type MediaModalTarget = 'primary' | 'gallery' | 'representative' | null;
type VariantRow = {
  id: string;
  label: string;
  supplierSku: string;
  available: boolean;
  imageUrl: string | null;
};
type SpecificationRow = {
  id: string;
  key: string;
  value: string;
};

const SPEC_TEMPLATE_BY_SLUG: Record<string, string[]> = {
  drilling: ['Brand', 'Condition', 'Drill Diameter', 'Hole Depth', 'Power Source', 'Operating Weight'],
  'underground-mining-vehicles': ['Brand', 'Condition', 'Payload Capacity', 'Engine Power', 'Operating Weight', 'Dimensions'],
  ventilation: ['Brand', 'Condition', 'Airflow Capacity', 'Power Requirement', 'Fan Diameter', 'Noise Level'],
  'load-haul-dump-lhd-loaders': ['Brand', 'Condition', 'Bucket Capacity', 'Payload Capacity', 'Engine Power', 'Operating Weight'],
  excavators: ['Brand', 'Condition', 'Bucket Capacity', 'Engine Power', 'Operating Weight', 'Digging Depth'],
  'water-truck': ['Brand', 'Condition', 'Tank Capacity', 'Engine Power', 'Operating Weight', 'Drive Type'],
};

const FIELD_CLASSNAME =
  'h-[42px] rounded-[4px] border border-[#b6c0c6] bg-white px-4 text-[15px] text-[#48636c] outline-none transition focus:border-[#62808a] focus:ring-0';
const SECTION_CLASSNAME = 'rounded-[8px] border border-[#eef1f3] bg-white px-6 py-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]';
const SECTION_ACCENT_CLASSNAME =
  'rounded-[8px] border border-[#eef1f3] border-t-[5px] border-t-[#375760] bg-white px-6 py-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]';

const REP_DAY_ORDER: { key: ProductRepresentativeDayKey; label: string }[] = [
  { key: 'mon', label: 'Mon' },
  { key: 'tue', label: 'Tue' },
  { key: 'wed', label: 'Wed' },
  { key: 'thu', label: 'Thu' },
  { key: 'fri', label: 'Fri' },
  { key: 'sat', label: 'Sat' },
  { key: 'sun', label: 'Sun' },
];

function ProductRepresentativeFields({
  intro,
  repName,
  setRepName,
  repEmail,
  setRepEmail,
  repMobile,
  setRepMobile,
  repImageMedia,
  repImageUploading,
  onRemoveRepImage,
  onBrowseRepresentativeLibrary,
  onUploadClick,
  repAvailability,
  setRepAvailability,
  onClearAll,
  showClearButton,
}: {
  intro: string;
  repName: string;
  setRepName: (v: string) => void;
  repEmail: string;
  setRepEmail: (v: string) => void;
  repMobile: string;
  setRepMobile: (v: string) => void;
  repImageMedia: MediaSelection | null;
  repImageUploading: boolean;
  onRemoveRepImage: () => void;
  onBrowseRepresentativeLibrary: () => void;
  onUploadClick: () => void;
  repAvailability: RepresentativeAvailabilityState;
  setRepAvailability: Dispatch<SetStateAction<RepresentativeAvailabilityState>>;
  onClearAll: () => void;
  showClearButton: boolean;
}): JSX.Element {
  return (
    <div>
      {intro ? <p className="text-[13px] text-[#9aa4ab] sm:text-[14px]">{intro}</p> : null}
      <div className={intro ? 'mt-4 grid gap-6 lg:grid-cols-2' : 'grid gap-6 lg:grid-cols-2'}>
        <div className="space-y-3">
          <div>
            <p className="mb-2 text-[15px] font-semibold text-[#466974]">Representative photo</p>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
              <div className="relative h-28 w-28 shrink-0 overflow-hidden rounded-[4px] border border-[#cfd8dc] bg-[#f8fbfc]">
                {repImageMedia?.url ? (
                  <>
                    <Image
                      src={repImageMedia.url}
                      alt="Representative"
                      fill
                      sizes="112px"
                      className="object-cover"
                      unoptimized
                    />
                    <button
                      type="button"
                      onClick={onRemoveRepImage}
                      className="absolute right-1 top-1 inline-flex h-7 w-7 items-center justify-center rounded-full bg-white/95 text-[#2f3d45] shadow hover:bg-white"
                      aria-label="Remove representative photo"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </>
                ) : (
                  <div className="flex h-full items-center justify-center px-2 text-center text-[12px] text-[#8a979d]">
                    No photo
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={onBrowseRepresentativeLibrary}
                  className="rounded-[4px] border border-[#bfd0d6] bg-[#f8fbfc] px-3 py-2 text-[13px] font-medium text-[#486a74]"
                >
                  Browse library
                </button>
                <button
                  type="button"
                  onClick={onUploadClick}
                  disabled={repImageUploading}
                  className="inline-flex items-center gap-2 rounded-[4px] border border-[#bfd0d6] bg-white px-3 py-2 text-[13px] font-medium text-[#486a74] disabled:opacity-60"
                >
                  {repImageUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  {repImageUploading ? 'Uploading…' : 'Upload'}
                </button>
              </div>
            </div>
          </div>
          <label className="flex flex-col gap-2 text-[15px] font-semibold text-[#466974]">
            Name
            <input
              value={repName}
              onChange={(e) => setRepName(e.target.value)}
              autoComplete="name"
              className={FIELD_CLASSNAME}
            />
          </label>
          <label className="flex flex-col gap-2 text-[15px] font-semibold text-[#466974]">
            Email
            <input
              value={repEmail}
              onChange={(e) => setRepEmail(e.target.value)}
              type="email"
              autoComplete="email"
              className={FIELD_CLASSNAME}
            />
          </label>
          <label className="flex flex-col gap-2 text-[15px] font-semibold text-[#466974]">
            Mobile
            <input
              value={repMobile}
              onChange={(e) => setRepMobile(e.target.value)}
              type="tel"
              autoComplete="tel"
              className={FIELD_CLASSNAME}
            />
          </label>
        </div>
        <div>
          <p className="mb-2 text-[14px] font-semibold text-[#466974]">ViewRoom availability</p>
          <div className="overflow-x-auto rounded-[4px] border border-[#cfd8dc]">
            <table className="w-full min-w-[280px] border-collapse text-left text-[14px] text-[#4c6670]">
              <thead>
                <tr className="border-b border-[#e2e8ec] bg-[#f8fbfc]">
                  <th className="px-3 py-2 font-semibold text-[#466974]">Day</th>
                  <th className="px-3 py-2 font-semibold text-[#466974]">From</th>
                  <th className="px-3 py-2 font-semibold text-[#466974]">To</th>
                </tr>
              </thead>
              <tbody>
                {REP_DAY_ORDER.map(({ key, label }) => (
                  <tr key={key} className="border-b border-[#eef1f3] last:border-b-0">
                    <td className="px-3 py-2 font-medium">{label}</td>
                    <td className="px-2 py-1.5">
                      <input
                        type="time"
                        value={repAvailability[key].from}
                        onChange={(e) =>
                          setRepAvailability((prev) =>
                            applyRepresentativeAvailabilityChange(prev, key, 'from', e.target.value),
                          )
                        }
                        max={repAvailability[key].to || undefined}
                        className={`h-[38px] w-full min-w-[7rem] rounded-[4px] border border-[#b6c0c6] bg-white px-2 text-[14px] outline-none focus:border-[#62808a]`}
                      />
                    </td>
                    <td className="px-2 py-1.5">
                      <input
                        type="time"
                        value={repAvailability[key].to}
                        onChange={(e) =>
                          setRepAvailability((prev) =>
                            applyRepresentativeAvailabilityChange(prev, key, 'to', e.target.value),
                          )
                        }
                        min={repAvailability[key].from || undefined}
                        className={`h-[38px] w-full min-w-[7rem] rounded-[4px] border border-[#b6c0c6] bg-white px-2 text-[14px] outline-none focus:border-[#62808a]`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      {showClearButton ? (
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClearAll}
            className="rounded-[4px] border border-[#7d99a4] bg-white px-5 py-2 text-sm font-semibold text-[#4b636d] transition hover:bg-[#f1f5f6]"
          >
            Clear representative
          </button>
        </div>
      ) : null}
    </div>
  );
}

function CardSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <section className="overflow-hidden my-4 rounded-xl border border-[#d7e2e7] bg-white shadow-sm">
      <div className="border-b border-[#e1ecef] bg-[#f6fafb] px-6 py-4">
        <h2 className="text-base font-semibold text-[#123d4a]">{title}</h2>
        {description ? <p className="mt-1 text-sm text-[#56707a]">{description}</p> : null}
      </div>
      <div className="space-y-4 px-6 py-5">{children}</div>
    </section>
  );
}

const numberFromString = (value: string): number | undefined => {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const toSlugish = (value: string | null | undefined): string =>
  value
    ? value
        .trim()
        .toLowerCase()
        .replace(/&/g, 'and')
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
    : '';

const stripParenthetical = (value: string | null | undefined): string =>
  (value ?? '').replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();

const extractParenthetical = (value: string | null | undefined): string[] =>
  Array.from((value ?? '').matchAll(/\(([^)]*)\)/g))
    .map((match) => match[1]?.trim() ?? '')
    .filter(Boolean);

const singularizeToken = (value: string): string => {
  if (value.length <= 3) return value;
  if (value.endsWith('ies')) return `${value.slice(0, -3)}y`;
  if (value.endsWith('ves')) return `${value.slice(0, -3)}f`;
  if (value.endsWith('ses')) return value.slice(0, -2);
  if (value.endsWith('s') && !value.endsWith('ss')) return value.slice(0, -1);
  return value;
};

const buildMatchTokens = (value: string | null | undefined): string[] => {
  const variants = [value ?? '', stripParenthetical(value), ...extractParenthetical(value)];
  const tokens = variants.flatMap((item) =>
    toSlugish(item)
      .split('-')
      .map((token) => singularizeToken(token.trim()))
      .filter(Boolean),
  );

  return Array.from(new Set(tokens));
};

const buildMatchKey = (value: string | null | undefined): string =>
  buildMatchTokens(value).join('-');

const scoreLabelMatch = (
  desired: string | null | undefined,
  candidate: string | null | undefined,
): number => {
  const desiredKey = buildMatchKey(desired);
  const candidateKey = buildMatchKey(candidate);

  if (!desiredKey || !candidateKey) return 0;
  if (desiredKey === candidateKey) return 100;
  if (desiredKey.includes(candidateKey) || candidateKey.includes(desiredKey)) return 90;

  const desiredTokens = buildMatchTokens(desired);
  const candidateTokens = buildMatchTokens(candidate);
  const overlap = desiredTokens.filter((token) => candidateTokens.includes(token));
  if (overlap.length === 0) return 0;

  return Math.round((overlap.length / Math.max(desiredTokens.length, candidateTokens.length)) * 80);
};

const pickBestMatch = <T,>(
  desired: string | null | undefined,
  options: T[],
  getLabel: (option: T) => string | null | undefined,
): T | null => {
  let best: T | null = null;
  let bestScore = 0;

  options.forEach((option) => {
    const score = scoreLabelMatch(desired, getLabel(option));
    if (score > bestScore) {
      best = option;
      bestScore = score;
    }
  });

  return bestScore >= 60 ? best : null;
};

const formatAttributeLabel = (label: string): string =>
  label
    .split(/[_-]/)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');

const attributeValueToString = (value: unknown): string => {
  if (value === null || value === undefined) return 'N/A';
  const text = String(value).trim();
  return text.length > 0 ? text : 'N/A';
};

const truncateText = (value: string, maxLength = 220): string => {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength).trimEnd()}...`;
};

const toAttributeRecord = (
  value: RawScrapedProduct['attributes'],
): Record<string, string | null> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, string | null>;
};

const isLikelyScraperNoiseAttribute = (key: string, value: string | null): boolean => {
  const normalizedKey = key.replace(/\s+/g, ' ').trim();
  const normalizedValue = (value ?? '').replace(/\s+/g, ' ').trim();

  if (!normalizedKey || !normalizedValue) return true;
  if (normalizedKey.length > 60 || normalizedValue.length > 160) return true;
  if (/[.!?]$/.test(normalizedKey)) return true;
  if (normalizedKey.split(/\s+/).length > 7) return true;
  if (/^(the|with|optional|fully|industry|hydraulic|integrated|need|spin|spring|storage|offering|for handling)\b/i.test(normalizedKey)) {
    return true;
  }

  return false;
};

const cleanScrapedAttributes = (attributes: Record<string, string | null>): Record<string, string | null> =>
  Object.fromEntries(
    Object.entries(attributes)
      .map(([key, value]) => [key.trim(), typeof value === 'string' ? value.trim() : value] as const)
      .filter(([key, value]) => !isLikelyScraperNoiseAttribute(key, value)),
  );

const extractSpecificationAttributesFromDescription = (
  description: string | null | undefined,
): Record<string, string> => {
  if (!description) return {};

  const lines = description
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const specificationsIndex = lines.findIndex((line) => /^specifications$/i.test(line));
  if (specificationsIndex === -1) return {};

  const endIndex = lines.findIndex(
    (line, index) => index > specificationsIndex && /^(features|key features|productivity|gallery|brochures)$/i.test(line),
  );
  const specLines = lines.slice(specificationsIndex + 1, endIndex === -1 ? lines.length : endIndex);
  const attributes: Record<string, string> = {};

  for (let index = 0; index < specLines.length - 1; index += 1) {
    const label = specLines[index];
    const value = specLines[index + 1];
    if (!label || !value) continue;
    if (/^[A-Z0-9-]{2,}$/i.test(label) && index === 0) continue;
    if (label.length > 48 || value.length > 120) continue;
    if (/^(rated power|operating weight|tipping load|breakout force|net power|gross power|bucket capacity|payload|rated payload)$/i.test(label)) {
      attributes[label] = value;
      index += 1;
    }
  }

  return attributes;
};

const getScrapedProductKey = (product: ScrapedProduct, index: number): string => {
  const sourceHint = product.productUrl || product.docUrl || product.title || 'scraped';
  return `${sourceHint}-${index}`;
};

const getTaxonomyPathFromTree = (
  tree: PublicProductTaxonomyTreeItem[],
  input: {
    superCategoryId?: string | null;
    categoryId?: string | null;
    classId?: string | null;
    subClassId?: string | null;
  },
) => {
  let matchedSuper: PublicProductTaxonomyTreeItem | null = null;
  let matchedCategory: PublicProductTaxonomyTreeItem['categories'][number] | null = null;
  let matchedClass: PublicProductTaxonomyTreeItem['categories'][number]['classes'][number] | null = null;
  let matchedSubClass:
    | PublicProductTaxonomyTreeItem['categories'][number]['classes'][number]['subClasses'][number]
    | null = null;

  for (const superCategory of tree) {
    if (input.superCategoryId && superCategory.id === input.superCategoryId) {
      matchedSuper = superCategory;
    }

    for (const category of superCategory.categories) {
      if (input.categoryId && category.id === input.categoryId) {
        matchedSuper = superCategory;
        matchedCategory = category;
      }

      for (const className of category.classes) {
        if (input.classId && className.id === input.classId) {
          matchedSuper = superCategory;
          matchedCategory = category;
          matchedClass = className;
        }

        for (const subClass of className.subClasses) {
          if (input.subClassId && subClass.id === input.subClassId) {
            matchedSuper = superCategory;
            matchedCategory = category;
            matchedClass = className;
            matchedSubClass = subClass;
          }
        }
      }
    }
  }

  return {
    superCategory: matchedSuper,
    category: matchedCategory,
    className: matchedClass,
    subClass: matchedSubClass,
  };
};

const flattenVisibleSubcategoryOptions = (
  category:
    | PublicProductTaxonomyTreeItem['categories'][number]
    | null
    | undefined,
) =>
  (category?.classes ?? []).flatMap((className) => {
    if (className.subClasses.length === 0) {
      return [{
        id: className.id,
        name: className.name,
        slug: className.slug,
        classId: className.id,
        subClassId: null as string | null,
      }];
    }

    return className.subClasses.map((subClass) => ({
      id: subClass.id,
      name: subClass.name,
      slug: subClass.slug,
      classId: className.id,
      subClassId: subClass.id,
    }));
  });

const createClientId = (): string =>
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

const createVariantRow = (index: number): VariantRow => ({
  id: createClientId(),
  label: `Variant ${index}`,
  supplierSku: '',
  available: true,
  imageUrl: null,
});

const createSpecificationRow = (key = '', value = ''): SpecificationRow => ({
  id: createClientId(),
  key,
  value,
});

const normalizeSpecificationKey = (value: string): string =>
  value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[^a-z0-9 ]/g, '');

const stripHtml = (value: string): string =>
  value
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const truncateAtWord = (value: string, maxLength: number): string => {
  if (value.length <= maxLength) return value;
  const sliced = value.slice(0, maxLength).trim();
  const lastSpace = sliced.lastIndexOf(' ');
  return `${(lastSpace > 80 ? sliced.slice(0, lastSpace) : sliced).trim()}...`;
};

const normalizeShortDescription = (value: string | null | undefined): string => {
  const text = stripHtml(value ?? '');
  return text ? truncateAtWord(text, 500) : '';
};

const deriveShortDescription = (description: string | null | undefined): string => {
  const text = stripHtml(description ?? '');
  if (!text) return '';
  const sentenceMatch = text.match(/^.{80,260}?[.!?](?:\s|$)/);
  return truncateAtWord((sentenceMatch?.[0] ?? text).trim(), 260);
};

const decodeHtmlEntities = (value: string): string =>
  value
    .replace(/&quot;/gi, '"')
    .replace(/&#34;/gi, '"')
    .replace(/&amp;/gi, '&')
    .replace(/&#39;/gi, "'")
    .replace(/&#x27;/gi, "'")
    .replace(/&nbsp;/gi, ' ');

const normalizeScrapedUrl = (value: string | null | undefined): string | null => {
  if (!value) return null;
  const normalized = decodeHtmlEntities(value)
    .trim()
    .replace(/^["'\s]+|["'\s]+$/g, '')
    .replace(/["']+$/g, '');

  if (!normalized) return null;

  try {
    return new URL(normalized).toString();
  } catch {
    return normalized;
  }
};

const collectScrapedUrls = (value: string | Array<string | null> | null | undefined): string[] => {
  if (!value) return [];
  const values = Array.isArray(value) ? value : [value];
  return values
    .map((item) => normalizeScrapedUrl(item ?? null))
    .filter((item): item is string => Boolean(item))
    .filter((item, index, array) => array.indexOf(item) === index);
};

const normalizeScrapedImages = (product: RawScrapedProduct): string[] => {
  const candidates = [
    ...collectScrapedUrls(product.image_url),
    ...collectScrapedUrls(product.image_urls ?? []),
    ...(product.gallery_images ?? []),
    ...(product.images ?? []),
  ];

  return candidates
    .map((value) => normalizeScrapedUrl(value))
    .filter((value): value is string => Boolean(value))
    .filter((value, index, array) => array.indexOf(value) === index);
};

const normalizeScrapedVideos = (product: RawScrapedProduct): string[] => {
  const candidates = [
    ...collectScrapedUrls(product.video_url),
    ...collectScrapedUrls(product.video_urls ?? []),
  ];

  return candidates.filter((value, index, array) => array.indexOf(value) === index);
};

const normalizeScrapedTaxonomyNode = (
  value: RawScrapedProduct["super_category"],
): ScrapedTaxonomyNode | null => {
  if (!value) return null;
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? { name: trimmed } : null;
  }
  if (typeof value !== "object" || Array.isArray(value)) return null;

  const id = typeof value.id === "string" && value.id.trim() ? value.id.trim() : null;
  const name = typeof value.name === "string" && value.name.trim() ? value.name.trim() : null;
  const slug = typeof value.slug === "string" && value.slug.trim() ? value.slug.trim() : null;

  if (!id && !name && !slug) return null;
  return { id, name, slug };
};

const getScrapedTaxonomyLabel = (
  value: RawScrapedProduct["super_category"],
): string | null => normalizeScrapedTaxonomyNode(value)?.name ?? null;

const getScrapedTaxonomyId = (
  value: RawScrapedProduct["super_category"],
): string | null => normalizeScrapedTaxonomyNode(value)?.id ?? null;

const normalizeScrapedDocuments = (product: RawScrapedProduct): string[] => {
  const candidates = [
    ...collectScrapedUrls(product.document_urls ?? []),
    ...collectScrapedUrls(product.doc_url),
  ];

  return candidates.filter((value, index, array) => array.indexOf(value) === index);
};

const normalizeScrapedFacets = (product: RawScrapedProduct): RawScrapedFacet[] => {
  if (!Array.isArray(product.facets)) return [];

  return product.facets
    .filter((facet): facet is RawScrapedFacet => Boolean(facet && typeof facet === "object"))
    .map((facet) => ({
      facet_id:
        typeof facet.facet_id === "string" && facet.facet_id.trim() ? facet.facet_id.trim() : null,
      value:
        typeof facet.value === "string"
          ? facet.value.trim() || null
          : facet.value ?? null,
      value_type:
        typeof facet.value_type === "string" && facet.value_type.trim()
          ? facet.value_type.trim()
          : null,
      key: typeof facet.key === "string" && facet.key.trim() ? facet.key.trim() : null,
      label: typeof facet.label === "string" && facet.label.trim() ? facet.label.trim() : null,
      sort_order:
        typeof facet.sort_order === "number" && Number.isFinite(facet.sort_order)
          ? facet.sort_order
          : null,
    }));
};

const normalizeFacetPayloadKey = (value: string | null | undefined): string =>
  (value ?? '')
    .trim()
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();

const buildScrapedFacetValues = (
  facets: RawScrapedFacet[],
): FacetValueRecord => {
  const out: FacetValueRecord = {};

  facets.forEach((facet) => {
    const key = normalizeFacetPayloadKey(facet.key ?? facet.label);
    if (!key) return;

    const value = facet.value;
    if (value === null || value === undefined) return;
    if (typeof value === 'string' && value.trim().length === 0) return;

    const normalizedValue =
      typeof value === 'string' ? value.trim() : value;

    const existing = out[key];
    if (existing === undefined) {
      out[key] = normalizedValue;
      return;
    }

    const nextValues = [
      ...(Array.isArray(existing) ? existing : [String(existing)]),
      String(normalizedValue),
    ].filter((item, index, array) => array.indexOf(item) === index);

    out[key] = nextValues;
  });

  return out;
};

const normalizeFacetText = (value: unknown): string =>
  String(value ?? '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();

const facetRecordHasValue = (record: FacetValueRecord, key: string): boolean => {
  const value = record[key];
  if (Array.isArray(value)) return value.some((entry) => String(entry).trim().length > 0);
  return value !== undefined && value !== null && String(value).trim().length > 0;
};

const mergeFacetValueRecords = (...records: Array<FacetValueRecord | null | undefined>): FacetValueRecord => {
  const out: FacetValueRecord = {};

  records.forEach((record) => {
    Object.entries(record ?? {}).forEach(([key, value]) => {
      if (value === null || value === undefined) return;
      if (typeof value === 'string' && value.trim().length === 0) return;

      const existing = out[key];
      if (existing === undefined) {
        out[key] = value;
        return;
      }

      const values = [
        ...(Array.isArray(existing) ? existing : [String(existing)]),
        ...(Array.isArray(value) ? value.map(String) : [String(value)]),
      ]
        .map((entry) => entry.trim())
        .filter((entry, index, array) => entry.length > 0 && array.indexOf(entry) === index);

      out[key] = values.length === 1 ? values[0] : values;
    });
  });

  return out;
};

const collectFacetInferenceText = (
  product: ScrapedProduct,
  sourceEnrichment?: SourceEnrichmentPayload | null,
): string => {
  const chunks = [
    product.title,
    product.description,
    product.category,
    product.subcategory,
    product.productUrl,
    ...Object.entries(product.attributes).flatMap(([key, value]) => [key, value ?? '']),
    ...product.facets.flatMap((facet) => [
      facet.key ?? '',
      facet.label ?? '',
      facet.value === null || facet.value === undefined ? '' : String(facet.value),
    ]),
    sourceEnrichment?.title ?? '',
    sourceEnrichment?.description ?? '',
    sourceEnrichment?.application ?? '',
    ...(sourceEnrichment?.features ?? []),
    ...(sourceEnrichment?.specifications ?? []).flatMap((row) => [row.label, row.value]),
  ];

  return normalizeFacetText(chunks.filter(Boolean).join(' | '));
};

const inferCanonicalFacetValues = (
  product: ScrapedProduct,
  sourceEnrichment?: SourceEnrichmentPayload | null,
): FacetValueRecord => {
  const text = collectFacetInferenceText(product, sourceEnrichment);
  const inferred: FacetValueRecord = {};

  if (/\b(refurbished|remanufactured|reman|reconditioned|rebuilt|used)\b/.test(text)) {
    inferred[CANONICAL_OPTION_FACETS.condition.key] = 'Refurbished';
  } else if (/\b(new|newly manufactured|factory new|brand new)\b/.test(text)) {
    inferred[CANONICAL_OPTION_FACETS.condition.key] = 'New';
  }

  if (/\b(aftermarket|third party|third-party|non oem|non-oem)\b/.test(text)) {
    inferred[CANONICAL_OPTION_FACETS.oemAftermarket.key] = 'Aftermarket';
  } else if (/\b(oem|original equipment|genuine|factory original|oem original)\b/.test(text)) {
    inferred[CANONICAL_OPTION_FACETS.oemAftermarket.key] = 'OEM Original';
  }

  if (/\b(global|worldwide|international)\b/.test(text)) {
    inferred[CANONICAL_OPTION_FACETS.serviceRegion.key] = 'Global';
  } else if (/\b(usa|u\.s\.a\.|united states|north america|america|american|canada|mexico)\b/.test(text)) {
    inferred[CANONICAL_OPTION_FACETS.serviceRegion.key] = 'American';
  } else if (/\b(emea|europe|middle east|germany|sweden|africa)\b/.test(text)) {
    inferred[CANONICAL_OPTION_FACETS.serviceRegion.key] = text.includes('africa') ? 'Africa' : 'EMEA';
  } else if (/\b(asia pacific|asia-pacific|apac|australia|china|india|japan)\b/.test(text)) {
    inferred[CANONICAL_OPTION_FACETS.serviceRegion.key] = 'Asia-Pacific';
  }

  return inferred;
};

const normalizeCanonicalFacetOptions = (values: FacetValueRecord): FacetValueRecord => {
  const out = { ...values };
  const canonicalGroups = Object.values(CANONICAL_OPTION_FACETS);

  canonicalGroups.forEach(({ key, options }) => {
    const current = out[key];
    if (current === undefined) return;

    const selected = (Array.isArray(current) ? current : [current])
      .map((value) => {
        const normalized = normalizeFacetText(value);
        return options.find((option) => normalizeFacetText(option) === normalized) ?? String(value).trim();
      })
      .filter((value, index, array) => value.length > 0 && array.indexOf(value) === index);

    if (selected.length === 0) {
      delete out[key];
      return;
    }
    out[key] = selected.length === 1 ? selected[0] : selected;
  });

  return out;
};

const mergeWithInferredCanonicalFacets = (
  product: ScrapedProduct,
  sourceEnrichment?: SourceEnrichmentPayload | null,
): FacetValueRecord => {
  const existing = normalizeCanonicalFacetOptions(product.facetValues);
  const inferred = inferCanonicalFacetValues(product, sourceEnrichment);
  const missingInferred = Object.fromEntries(
    Object.entries(inferred).filter(([key]) => !facetRecordHasValue(existing, key)),
  ) as FacetValueRecord;

  return mergeFacetValueRecords(existing, missingInferred);
};

const normalizeScrapeProductsResponse = (payload: ScrapeProductsResponse | RawScrapedProduct): RawScrapedProduct[] => {
  if (Array.isArray((payload as ScrapeProductsResponse).products)) {
    return ((payload as ScrapeProductsResponse).products ?? []).filter(Boolean) as RawScrapedProduct[];
  }

  if ((payload as ScrapeProductsResponse).product && typeof (payload as ScrapeProductsResponse).product === 'object') {
    return [(payload as ScrapeProductsResponse).product as RawScrapedProduct];
  }

  if (payload && typeof payload === 'object' && ('title' in payload || 'product_url' in payload)) {
    return [payload as RawScrapedProduct];
  }

  return [];
};

const rowsToAttributeRecord = (
  rows: SourceEnrichmentPayload['specifications'],
): Record<string, string> =>
  rows.reduce<Record<string, string>>((accumulator, row) => {
    const key = row.label.trim();
    const value = row.value.trim();
    if (!key || !value) return accumulator;
    accumulator[key] = value;
    return accumulator;
  }, {});

const getSuggestedSpecificationKeys = (
  primaryNode: { slug?: string | null; name?: string | null } | null,
  secondaryNode: { slug?: string | null; name?: string | null } | null,
): string[] => {
  const lookupKeys = [secondaryNode?.slug, secondaryNode?.name, primaryNode?.slug, primaryNode?.name]
    .map((item) => toSlugish(item))
    .filter(Boolean);

  for (const key of lookupKeys) {
    const matched = SPEC_TEMPLATE_BY_SLUG[key];
    if (matched?.length) return matched;
  }

  return primaryNode || secondaryNode
    ? ['Brand', 'Condition', 'Model Year', 'Power Requirement', 'Operating Weight']
    : [];
};

export default function AddProductPage(): JSX.Element {
  const router = useRouter();
  const [microsite, setMicrosite] = useState<ApiMicrosite | null>(null);

  const [name, setName] = useState('');
  const [modelType, setModelType] = useState('');
  const [sku] = useState('');
  const [shortDescription, setShortDescription] = useState('');
  const [description, setDescription] = useState('');
  const [promoMessage] = useState('NULL');
  const [isFeatured] = useState(false);
  const [price, setPrice] = useState('');
  const [currency, setCurrency] = useState<(typeof CURRENCY_OPTIONS)[number]>('USD');
  const [stockQuantity, setStockQuantity] = useState('');
  const [dashboardSearch, setDashboardSearch] = useState('');
  const [variantRows, setVariantRows] = useState<VariantRow[]>([
    createVariantRow(1),
  ]);
  const [specificationRows, setSpecificationRows] = useState<SpecificationRow[]>([]);
  const [repRows, setRepRows] = useState<ProductRepFormRow[]>(() => [createEmptyProductRepFormRow()]);
  const repMediaRowIndexRef = useRef(0);
  const [repImageUploadingIndex, setRepImageUploadingIndex] = useState<number | null>(null);
  const [isDescriptionHtmlMode, setIsDescriptionHtmlMode] = useState(false);
  const [isDescriptionPreview, setIsDescriptionPreview] = useState(false);

  const [categoryOptions, setCategoryOptions] = useState<CategoryNode[]>([]);
  const [taxonomyOptions, setTaxonomyOptions] = useState<PublicProductTaxonomyTreeItem[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(false);
  const [categoriesError, setCategoriesError] = useState('');
  const [selectedSuperCategoryId, setSelectedSuperCategoryId] = useState('');
  const [selectedTaxonomyCategoryId, setSelectedTaxonomyCategoryId] = useState('');
  const [selectedTaxonomyClassId, setSelectedTaxonomyClassId] = useState('');
  const [selectedTaxonomySubClassId, setSelectedTaxonomySubClassId] = useState('');

  const [primaryMedia, setPrimaryMedia] = useState<MediaSelection | null>(null);
  const [galleryMedia, setGalleryMedia] = useState<MediaSelection[]>([]);
  const [mediaModalTarget, setMediaModalTarget] = useState<MediaModalTarget>(null);

  const [primaryUploading, setPrimaryUploading] = useState(false);
  const [galleryUploading, setGalleryUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [scrapedProducts, setScrapedProducts] = useState<ScrapedProduct[]>([]);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [scrapeError, setScrapeError] = useState('');
  const [isSavingScrapedProducts, setIsSavingScrapedProducts] = useState(false);
  const [scrapeSource, setScrapeSource] = useState('');
  const [isScrapeModalOpen, setIsScrapeModalOpen] = useState(false);
  const [scrapeUrl, setScrapeUrl] = useState(DEFAULT_SCRAPE_URL);
  const [scrapeUrlError, setScrapeUrlError] = useState('');
  const [savingProductKeys, setSavingProductKeys] = useState<string[]>([]);
  const [expandedScrapedDescriptions, setExpandedScrapedDescriptions] = useState<string[]>([]);

  const primaryInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const repImageInputRef = useRef<HTMLInputElement>(null);
  const descriptionEditorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setCategoriesLoading(true);
      try {
        const site = await fetchSupplierMicrosite();
        if (!active) return;
        if (!site) {
          setMicrosite(null);
          setCategoryOptions([]);
          setCategoriesError('No supplier microsite found. Create one to manage products.');
          return;
        }
        setMicrosite(site);
        const [{ categories }, taxonomy] = await Promise.all([
          fetchProductCategories(),
          fetchPublicProductTaxonomy(),
        ]);
        if (!active) return;
        setCategoryOptions(categories.map((cat) => ({ ...cat, children: cat.children ?? [] })));
        setTaxonomyOptions(taxonomy);
        setCategoriesError('');
      } catch (err) {
        console.error('Failed to load product categories', err);
        if (active) {
          setCategoryOptions([]);
          setTaxonomyOptions([]);
          setCategoriesError('Unable to load product categories.');
        }
      } finally {
        if (active) setCategoriesLoading(false);
      }
    };

    void load();
    return () => {
      active = false;
    };
  }, []);

  const selectedSuperCategory = useMemo(
    () => taxonomyOptions.find((option) => option.id === selectedSuperCategoryId) ?? null,
    [taxonomyOptions, selectedSuperCategoryId],
  );
  const taxonomyCategoryOptions = useMemo(
    () => selectedSuperCategory?.categories ?? [],
    [selectedSuperCategory],
  );
  const selectedTaxonomyCategory = useMemo(
    () => taxonomyCategoryOptions.find((option) => option.id === selectedTaxonomyCategoryId) ?? null,
    [taxonomyCategoryOptions, selectedTaxonomyCategoryId],
  );
  const taxonomyClassOptions = useMemo(
    () => selectedTaxonomyCategory?.classes ?? [],
    [selectedTaxonomyCategory],
  );
  const selectedTaxonomyClass = useMemo(
    () => taxonomyClassOptions.find((option) => option.id === selectedTaxonomyClassId) ?? null,
    [taxonomyClassOptions, selectedTaxonomyClassId],
  );
  const taxonomySubClassOptions = useMemo(
    () => selectedTaxonomyClass?.subClasses ?? [],
    [selectedTaxonomyClass],
  );
  const selectedTaxonomySubClass = useMemo(
    () => taxonomySubClassOptions.find((option) => option.id === selectedTaxonomySubClassId) ?? null,
    [taxonomySubClassOptions, selectedTaxonomySubClassId],
  );
  const visibleSubcategoryOptions = useMemo(
    () => flattenVisibleSubcategoryOptions(selectedTaxonomyCategory),
    [selectedTaxonomyCategory],
  );
  const selectedVisibleSubcategoryId = selectedTaxonomySubClassId || selectedTaxonomyClassId;
  const suggestedSpecificationKeys = useMemo(
    () =>
      getSuggestedSpecificationKeys(
        selectedTaxonomySubClass ?? selectedTaxonomyClass ?? selectedTaxonomyCategory ?? selectedSuperCategory,
        selectedTaxonomyClass ?? selectedTaxonomyCategory ?? selectedSuperCategory,
      ),
    [
      selectedSuperCategory,
      selectedTaxonomyCategory,
      selectedTaxonomyClass,
      selectedTaxonomySubClass,
    ],
  );
  const descriptionPlainText = useMemo(() => stripHtml(description), [description]);

  const scrapeSourceHost = useMemo(() => {
    if (!scrapeSource) return '';
    try {
      return new URL(scrapeSource).hostname;
    } catch {
      return scrapeSource;
    }
  }, [scrapeSource]);

  useEffect(() => {
    if (!selectedSuperCategoryId) {
      setSelectedTaxonomyCategoryId('');
      setSelectedTaxonomyClassId('');
      setSelectedTaxonomySubClassId('');
      return;
    }
    if (!taxonomyCategoryOptions.some((item) => item.id === selectedTaxonomyCategoryId)) {
      setSelectedTaxonomyCategoryId('');
      setSelectedTaxonomyClassId('');
      setSelectedTaxonomySubClassId('');
    }
  }, [selectedSuperCategoryId, selectedTaxonomyCategoryId, taxonomyCategoryOptions]);

  useEffect(() => {
    if (!selectedTaxonomyCategoryId) {
      setSelectedTaxonomyClassId('');
      setSelectedTaxonomySubClassId('');
      return;
    }
    const isValidVisibleSelection = visibleSubcategoryOptions.some(
      (item) => item.classId === selectedTaxonomyClassId && item.subClassId === selectedTaxonomySubClassId,
    );
    if (!isValidVisibleSelection) {
      setSelectedTaxonomyClassId('');
      setSelectedTaxonomySubClassId('');
    }
  }, [selectedTaxonomyCategoryId, selectedTaxonomyClassId, selectedTaxonomySubClassId, visibleSubcategoryOptions]);

  const mediaStripItems = useMemo(() => {
    const items = [
      ...(primaryMedia ? [primaryMedia] : []),
      ...galleryMedia,
    ].filter((item, index, array) => array.findIndex((candidate) => candidate.url === item.url) === index);

    return items.slice(0, Math.max(MAX_GALLERY_IMAGES, 8));
  }, [galleryMedia, primaryMedia]);

  useEffect(() => {
    setVariantRows((current) =>
      current.map((row, index) => ({
        ...row,
        imageUrl:
          row.imageUrl && mediaStripItems.some((item) => item.url === row.imageUrl)
            ? row.imageUrl
            : mediaStripItems[index]?.url ?? null,
      })),
    );
  }, [mediaStripItems]);

  useEffect(() => {
    setSpecificationRows((current) => {
      if (!suggestedSpecificationKeys.length) return current;

      const existing = new Set(current.map((row) => normalizeSpecificationKey(row.key)));
      const additions = suggestedSpecificationKeys
        .filter((key) => !existing.has(normalizeSpecificationKey(key)))
        .map((key) => createSpecificationRow(key, ''));

      return additions.length > 0 ? [...current, ...additions] : current;
    });
  }, [suggestedSpecificationKeys]);

  useEffect(() => {
    if (!descriptionEditorRef.current || isDescriptionHtmlMode || isDescriptionPreview) return;
    if (descriptionEditorRef.current.innerHTML !== description) {
      descriptionEditorRef.current.innerHTML = description;
    }
  }, [description, isDescriptionHtmlMode, isDescriptionPreview]);

  const openMediaModal = (target: Exclude<MediaModalTarget, null>) => {
    setMediaModalTarget(target);
  };

  const handleMediaInsert = (items: SelectedMediaFile[]) => {
    if (!items.length || !mediaModalTarget) {
      setMediaModalTarget(null);
      return;
    }

    if (mediaModalTarget === 'primary') {
      const [first] = items;
      setPrimaryMedia(first ? { id: first.id, url: first.src } : null);
    } else if (mediaModalTarget === 'representative') {
      const [first] = items;
      const idx = repMediaRowIndexRef.current;
      setRepRows((prev) =>
        prev.map((row, i) =>
          i === idx ? { ...row, imageMedia: first ? { id: first.id, url: first.src } : null } : row,
        ),
      );
    } else {
      setGalleryMedia((prev) => {
        const combined = [...prev];
        items.forEach((item) => {
          if (!combined.some((existing) => existing.url === item.src)) {
            combined.push({ id: item.id, url: item.src });
          }
        });
        return combined.slice(0, MAX_GALLERY_IMAGES);
      });
    }

    setMediaModalTarget(null);
  };

  const handlePrimaryUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setPrimaryUploading(true);
    try {
      const resource: MediaResource = await replaceMedia(primaryMedia?.id, file);
      setPrimaryMedia({ id: resource.id, url: resource.url });
      enqueueSnackbar('Primary image updated.', { variant: 'success' });
    } catch (error) {
      console.error('Failed to upload primary image', error);
      enqueueSnackbar('Failed to upload primary image.', { variant: 'error' });
    } finally {
      setPrimaryUploading(false);
    }
  };

  const handleGalleryUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    event.target.value = '';
    if (!files || files.length === 0) return;

    setGalleryUploading(true);
    try {
      const uploaded = await uploadMany(Array.from(files));
      setGalleryMedia((prev) => {
        const combined = [...prev];
        uploaded.forEach((item) => {
          if (!combined.some((existing) => existing.url === item.url)) {
            combined.push({ id: item.id, url: item.url });
          }
        });
        return combined.slice(0, MAX_GALLERY_IMAGES);
      });
      enqueueSnackbar(
        `Added ${uploaded.length} gallery image${uploaded.length > 1 ? 's' : ''}.`,
        { variant: 'success' },
      );
    } catch (error) {
      console.error('Failed to upload gallery images', error);
      enqueueSnackbar('Failed to upload gallery images.', { variant: 'error' });
    } finally {
      setGalleryUploading(false);
    }
  };

  const removePrimaryImage = () => setPrimaryMedia(null);
  const handleRepImageUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    const idx = repMediaRowIndexRef.current;
    const existingId = repRows[idx]?.imageMedia?.id;
    setRepImageUploadingIndex(idx);
    try {
      const resource: MediaResource = await replaceMedia(existingId, file);
      setRepRows((prev) =>
        prev.map((row, i) =>
          i === idx ? { ...row, imageMedia: { id: resource.id, url: resource.url } } : row,
        ),
      );
      enqueueSnackbar('Representative photo updated.', { variant: 'success' });
    } catch (error) {
      console.error('Failed to upload representative photo', error);
      enqueueSnackbar('Failed to upload representative photo.', { variant: 'error' });
    } finally {
      setRepImageUploadingIndex(null);
    }
  };
  const removeGalleryImage = (url: string) =>
    setGalleryMedia((prev) => prev.filter((item) => item.url !== url));
  const handleSelectPrimaryImage = (url: string) => {
    const matched =
      mediaStripItems.find((item) => item.url === url) ??
      galleryMedia.find((item) => item.url === url) ??
      null;

    if (matched) {
      setPrimaryMedia(matched);
    }
  };

  const handleVariantSkuChange = (id: string, value: string) => {
    setVariantRows((current) =>
      current.map((row) => (row.id === id ? { ...row, supplierSku: value.slice(0, 200) } : row)),
    );
  };

  const handleVariantLabelChange = (id: string, value: string) => {
    setVariantRows((current) =>
      current.map((row) => (row.id === id ? { ...row, label: value } : row)),
    );
  };

  const handleVariantImageChange = (id: string, value: string) => {
    setVariantRows((current) =>
      current.map((row) =>
        row.id === id
          ? {
              ...row,
              imageUrl: value || null,
            }
          : row,
      ),
    );
  };

  const handleVariantAvailabilityChange = (id: string) => {
    setVariantRows((current) =>
      current.map((row) => (row.id === id ? { ...row, available: !row.available } : row)),
    );
  };

  const handleAddVariantRow = () => {
    setVariantRows((current) => [...current, createVariantRow(current.length + 1)]);
  };

  const handleRemoveVariantRow = (id: string) => {
    setVariantRows((current) => (current.length > 1 ? current.filter((row) => row.id !== id) : current));
  };

  const handleSpecificationChange = (
    id: string,
    field: keyof Pick<SpecificationRow, 'key' | 'value'>,
    value: string,
  ) => {
    setSpecificationRows((current) =>
      current.map((row) => (row.id === id ? { ...row, [field]: value } : row)),
    );
  };

  const handleAddSpecificationRow = (key = '') => {
    setSpecificationRows((current) => [...current, createSpecificationRow(key)]);
  };

  const handleRemoveSpecificationRow = (id: string) => {
    setSpecificationRows((current) => current.filter((row) => row.id !== id));
  };

  const handleDescriptionInput = () => {
    setDescription(descriptionEditorRef.current?.innerHTML ?? '');
  };

  const runDescriptionCommand = (command: string, value?: string) => {
    if (isDescriptionHtmlMode || isDescriptionPreview) {
      setIsDescriptionHtmlMode(false);
      setIsDescriptionPreview(false);
    }

    descriptionEditorRef.current?.focus();
    document.execCommand(command, false, value);
    handleDescriptionInput();
  };

  const handleInsertDescriptionImage = () => {
    const imageUrl =
      primaryMedia?.url ||
      mediaStripItems[0]?.url ||
      window.prompt('Enter image URL to insert into the description');

    if (!imageUrl) return;
    runDescriptionCommand('insertImage', imageUrl);
  };

  const findMatchingCategory = (
    categoryName: string | null | undefined,
    subcategoryName: string | null | undefined,
  ) => {
    if (!categoryName) return { category: null, subcategory: null };
    const categoryMatch =
      pickBestMatch(
        categoryName,
        categoryOptions,
        (option) => option.slug ?? option.name,
      ) ??
      pickBestMatch(categoryName, categoryOptions, (option) => option.name) ??
      null;

    if (!categoryMatch) return { category: null, subcategory: null };
    if (!subcategoryName) {
      return { category: categoryMatch, subcategory: null };
    }

    const subcategoryMatch =
      pickBestMatch(
        subcategoryName,
        categoryMatch.children,
        (child) => child.slug ?? child.name,
      ) ??
      pickBestMatch(subcategoryName, categoryMatch.children, (child) => child.name) ??
      null;

    if (subcategoryMatch) {
      return { category: categoryMatch, subcategory: subcategoryMatch };
    }

    const globalSubcategoryMatch = categoryOptions
      .map((option) => ({
        category: option,
        subcategory:
          pickBestMatch(subcategoryName, option.children, (child) => child.slug ?? child.name) ??
          pickBestMatch(subcategoryName, option.children, (child) => child.name),
      }))
      .find((entry) => entry.subcategory);

    if (globalSubcategoryMatch?.subcategory) {
      return {
        category: globalSubcategoryMatch.category,
        subcategory: globalSubcategoryMatch.subcategory,
      };
    }

    return { category: categoryMatch, subcategory: null };
  };

  const clearScrapedProducts = () => {
    setScrapedProducts([]);
    setSavingProductKeys([]);
    setExpandedScrapedDescriptions([]);
    setScrapeError('');
    setScrapeSource('');
  };

  const applyVisibleSubcategorySelection = useCallback(
    (
      value: string,
      currentCategory: PublicProductTaxonomyTreeItem['categories'][number] | null | undefined,
    ) => {
      const matched = flattenVisibleSubcategoryOptions(currentCategory).find((item) => item.id === value);
      setSelectedTaxonomyClassId(matched?.classId ?? '');
      setSelectedTaxonomySubClassId(matched?.subClassId ?? '');
    },
    [],
  );

  const updateScrapedProductTaxonomy = useCallback(
    (
      index: number,
      field: 'superCategoryId' | 'taxonomyCategoryId' | 'visibleSubcategoryId',
      value: string,
    ) => {
      setScrapedProducts((current) =>
        current.map((product, itemIndex) => {
          if (itemIndex !== index) return product;

          if (field === 'superCategoryId') {
            const nextSuper = taxonomyOptions.find((item) => item.id === value) ?? null;
            return {
              ...product,
              superCategoryId: value || null,
              taxonomyCategoryId: null,
              taxonomyClassId: null,
              taxonomySubClassId: null,
              sourceTaxonomy: {
                ...product.sourceTaxonomy,
                superCategory: nextSuper
                  ? { id: nextSuper.id, name: nextSuper.name, slug: nextSuper.slug }
                  : null,
                category: null,
                className: null,
                subClass: null,
              },
            };
          }

          const currentPath = getTaxonomyPathFromTree(taxonomyOptions, {
            superCategoryId: product.superCategoryId,
            categoryId: product.taxonomyCategoryId,
            classId: product.taxonomyClassId,
            subClassId: product.taxonomySubClassId,
          });

          if (field === 'taxonomyCategoryId') {
            const nextCategory =
              currentPath.superCategory?.categories.find((item) => item.id === value) ?? null;
            return {
              ...product,
              taxonomyCategoryId: value || null,
              taxonomyClassId: null,
              taxonomySubClassId: null,
              sourceTaxonomy: {
                ...product.sourceTaxonomy,
                category: nextCategory
                  ? { id: nextCategory.id, name: nextCategory.name, slug: nextCategory.slug }
                  : null,
                className: null,
                subClass: null,
              },
            };
          }

          const nextVisibleSubcategory = flattenVisibleSubcategoryOptions(currentPath.category).find(
            (item) => item.id === value,
          );
          const nextClass =
            currentPath.category?.classes.find((item) => item.id === nextVisibleSubcategory?.classId) ?? null;
          const nextSubClass =
            nextClass?.subClasses.find((item) => item.id === nextVisibleSubcategory?.subClassId) ?? null;
          return {
            ...product,
            taxonomyClassId: nextClass?.id ?? null,
            taxonomySubClassId: nextSubClass?.id ?? null,
            sourceTaxonomy: {
              ...product.sourceTaxonomy,
              className: nextClass
                ? { id: nextClass.id, name: nextClass.name, slug: nextClass.slug }
                : null,
              subClass: nextSubClass
                ? { id: nextSubClass.id, name: nextSubClass.name, slug: nextSubClass.slug }
                : null,
            },
          };
        }),
      );
    },
    [taxonomyOptions],
  );

  const handleScrapeProducts = async (productUrl: string): Promise<boolean> => {
    const trimmedUrl = productUrl.trim();
    if (!trimmedUrl) {
      setScrapeError('Please provide a product URL to scrape.');
      return false;
    }

    setScrapeError('');
    setScrapeSource('');
    setScrapeLoading(true);
    try {
      const response = await fetch('https://news.mininglifeserver.com/scrape-products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_url: trimmedUrl }),
      });

      if (!response.ok) {
        throw new Error(
          `Scrape request failed with status ${response.status}${
            response.statusText ? ` (${response.statusText})` : ''
          }`,
        );
      }

      const data = (await response.json()) as ScrapeProductsResponse | RawScrapedProduct;
      const items = normalizeScrapeProductsResponse(data);

      if (items.length === 0) {
        setScrapedProducts([]);
        setSavingProductKeys([]);
        const message = 'No product was returned from the scrape request.';
        setScrapeError(message);
        enqueueSnackbar('No product found at the provided URL.', { variant: 'warning' });
        return false;
      }

      const normalizedProducts: ScrapedProduct[] = items.map((item) => {
        const description = (item.description ?? '').trim();
        const scrapedShortDescription = normalizeShortDescription(
          item.shortDescription ?? item.short_description ?? item.summary,
        );
        const descriptionAttributes = extractSpecificationAttributesFromDescription(description);
        const cleanedAttributes = cleanScrapedAttributes(toAttributeRecord(item.attributes));
        const attributes = Object.keys(descriptionAttributes).length
          ? descriptionAttributes
          : cleanedAttributes;
        const imageUrls = normalizeScrapedImages(item);
        const videoUrls = normalizeScrapedVideos(item);
        const documentUrls = normalizeScrapedDocuments(item);
        const facets = normalizeScrapedFacets(item);
        const normalizedProductUrl = normalizeScrapedUrl(item.product_url) ?? normalizeScrapedUrl(trimmedUrl);
        const normalizedDocUrl = documentUrls[0] ?? null;
        const rawSuperCategory = item.cluster ?? item.super_category;
        const rawClass = item.class ?? item.class_name;
        const rawSubClass = item.sub_class ?? item.sub_class_name ?? item.subcategory;
        const superCategory = normalizeScrapedTaxonomyNode(rawSuperCategory);
        const taxonomyCategory = normalizeScrapedTaxonomyNode(item.category);
        const taxonomyClass = normalizeScrapedTaxonomyNode(rawClass);
        const taxonomySubClass = normalizeScrapedTaxonomyNode(rawSubClass);
        return {
          title: (item.title ?? '').trim() || 'Untitled Product',
          shortDescription: scrapedShortDescription || deriveShortDescription(description),
          description,
          imageUrl: imageUrls[0] ?? null,
          imageUrls,
          videoUrls,
          docUrl: normalizedDocUrl,
          documentUrls,
          category: getScrapedTaxonomyLabel(item.category),
          subcategory: getScrapedTaxonomyLabel(rawSubClass),
          superCategoryId: getScrapedTaxonomyId(rawSuperCategory),
          taxonomyCategoryId: getScrapedTaxonomyId(item.category),
          taxonomyClassId: getScrapedTaxonomyId(rawClass),
          taxonomySubClassId: getScrapedTaxonomyId(rawSubClass),
          sourceTaxonomy: {
            superCategory,
            category: taxonomyCategory,
            className: taxonomyClass,
            subClass: taxonomySubClass,
          },
          facets,
          facetValues: buildScrapedFacetValues(facets),
          attributes,
          productUrl: normalizedProductUrl,
        };
      });

      setScrapedProducts(normalizedProducts);
      setSavingProductKeys([]);
      setScrapeSource(
        normalizeScrapedUrl((data as ScrapeProductsResponse).source_url) ??
          normalizedProducts[0]?.productUrl ??
          trimmedUrl,
      );
      enqueueSnackbar(
        `Fetched ${normalizedProducts.length} scraped product${
          normalizedProducts.length === 1 ? '' : 's'
        } from the source URL.`,
        { variant: 'success' },
      );
      return true;
    } catch (error) {
      console.error('Failed to scrape products', error);
      const message =
        (error instanceof Error && error.message) ||
        'Unable to scrape products. Please try again.';
      setScrapeError(message);
      setScrapeSource('');
      enqueueSnackbar(message, { variant: 'error' });
      return false;
    } finally {
      setScrapeLoading(false);
    }
  };

  const persistScrapedProduct = async (product: ScrapedProduct, micrositeId: string) => {
    const { category, subcategory } = findMatchingCategory(product.category, product.subcategory);
    const hasScrapedTaxonomySelection =
      Boolean(product.superCategoryId) ||
      Boolean(product.taxonomyCategoryId) ||
      Boolean(product.taxonomyClassId) ||
      Boolean(product.taxonomySubClassId);
    let sourceEnrichment: SourceEnrichmentPayload | null = null;

    if (product.productUrl) {
      try {
        const response = await fetch(`/api/product-source?url=${encodeURIComponent(product.productUrl)}`, {
          cache: 'no-store',
        });

        if (response.ok) {
          sourceEnrichment = (await response.json()) as SourceEnrichmentPayload;
        }
      } catch (error) {
        console.error('Failed to enrich scraped product source', error);
      }
    }

    const enrichedAttributes = {
      ...product.attributes,
      ...rowsToAttributeRecord(sourceEnrichment?.specifications ?? []),
    };
    const facetValuesPayload = mergeWithInferredCanonicalFacets(product, sourceEnrichment);

    const attributeEntries = Object.entries(enrichedAttributes).filter(
      ([, value]) => value !== null && value !== undefined && String(value).trim().length > 0,
    );

    const mergedImages = [...product.imageUrls, ...(sourceEnrichment?.images ?? [])].filter(
      (value, index, array) => array.indexOf(value) === index,
    );

    const attributesPayload =
      attributeEntries.length > 0 ? Object.fromEntries(attributeEntries) : undefined;

    const specificationsPayload =
      attributesPayload ||
      product.productUrl ||
      product.docUrl ||
      product.documentUrls.length ||
      product.videoUrls.length ||
      mergedImages.length ||
      product.facets.length ||
      product.superCategoryId ||
      product.taxonomyCategoryId ||
      product.taxonomyClassId ||
      product.taxonomySubClassId ||
      sourceEnrichment?.features?.length ||
      sourceEnrichment?.application ||
      sourceEnrichment?.description
        ? {
            ...(attributesPayload ? { attributes: attributesPayload } : {}),
            ...(product.category ? { sourceCategory: product.category } : {}),
            ...(product.subcategory ? { sourceSubcategory: product.subcategory } : {}),
            ...(product.productUrl
              ? {
                  productUrl: product.productUrl,
                  sourceUrl: product.productUrl,
                }
              : {}),
            ...(product.docUrl
              ? {
                  docUrl: product.docUrl,
                  documentationUrl: product.docUrl,
                }
              : {}),
            ...(product.documentUrls.length
              ? {
                  documents: product.documentUrls,
                  documentUrls: product.documentUrls,
                }
              : {}),
            ...(product.videoUrls.length ? { videoUrls: product.videoUrls } : {}),
            ...(mergedImages.length ? { sourceImageUrls: mergedImages } : {}),
            ...(product.sourceTaxonomy.superCategory ||
            product.sourceTaxonomy.category ||
            product.sourceTaxonomy.className ||
            product.sourceTaxonomy.subClass
              ? {
                  sourceTaxonomy: product.sourceTaxonomy,
                }
              : {}),
            ...(product.facets.length ? { sourceFacets: product.facets } : {}),
            ...(Object.keys(facetValuesPayload).length
              ? { sourceFacetValues: facetValuesPayload }
              : {}),
            ...(sourceEnrichment?.features?.length
              ? { sourceFeatures: sourceEnrichment.features }
              : {}),
            ...(sourceEnrichment?.application
              ? { sourceApplication: sourceEnrichment.application }
              : {}),
            ...(sourceEnrichment?.description
              ? { sourceDescription: sourceEnrichment.description }
              : {}),
          }
        : undefined;

    const payload: CreateProductPayload = {
      micrositeId,
      name: product.title,
      shortDescription:
        normalizeShortDescription(sourceEnrichment?.description) ||
        normalizeShortDescription(product.shortDescription) ||
        deriveShortDescription(product.description) ||
        undefined,
      description: sourceEnrichment?.description || product.description || undefined,
      primaryImageUrl: mergedImages[0] ?? product.imageUrl,
      galleryImages: mergedImages.slice(1),
      status: 'PUBLISHED',
      isFeatured: false,
      superCategoryId: product.superCategoryId,
      taxonomyCategoryId: product.taxonomyCategoryId,
      taxonomyClassId: product.taxonomyClassId,
      taxonomySubClassId: product.taxonomySubClassId,
      categoryId: hasScrapedTaxonomySelection ? null : category?.id ?? null,
      subcategoryId: hasScrapedTaxonomySelection ? null : subcategory?.id ?? null,
      facetValues: Object.keys(facetValuesPayload).length ? facetValuesPayload : undefined,
      specifications: specificationsPayload,
      representative: buildRepresentativesPayloadForApi(repRows),
      currency: 'USD',
      stockQuantity: 0,
      promoMessage: 'NULL',
    };

    await createProduct(payload);
  };

  const handleSaveScrapedProduct = async (product: ScrapedProduct, index: number) => {
    if (!microsite) {
      const message = 'You need an active supplier microsite before saving scraped products.';
      setScrapeError(message);
      enqueueSnackbar(message, { variant: 'warning' });
      return;
    }

    const key = getScrapedProductKey(product, index);
    setSavingProductKeys((prev) => [...prev, key]);

    try {
      await persistScrapedProduct(product, microsite.id);
      setScrapedProducts((prev) => {
        const next = prev.filter((_, idx) => idx !== index);
        if (next.length === 0) {
          setScrapeSource('');
        }
        return next;
      });
      enqueueSnackbar('Product saved to your catalogue.', { variant: 'success' });
    } catch (error) {
      console.error('Failed to save scraped product', error);
      const message =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        (error instanceof Error ? error.message : undefined) ??
        'Unable to save scraped product.';
      setScrapeError(message);
      enqueueSnackbar(message, { variant: 'error' });
    } finally {
      setSavingProductKeys((prev) => prev.filter((value) => value !== key));
    }
  };

  const handleOpenScrapeModal = () => {
    setScrapeUrlError('');
    setIsScrapeModalOpen(true);
  };

  const handleCloseScrapeModal = () => {
    if (!scrapeLoading) {
      setIsScrapeModalOpen(false);
    }
  };

  const handleScrapeSubmit = async () => {
    if (scrapeLoading) return;
    const trimmed = scrapeUrl.trim();
    if (!trimmed) {
      setScrapeUrlError('Please paste a product URL to scrape.');
      return;
    }

    setScrapeUrlError('');
    setScrapeUrl(trimmed);
    const success = await handleScrapeProducts(trimmed);
    if (success) {
      setIsScrapeModalOpen(false);
    }
  };

  const handleSaveScrapedProducts = async () => {
    if (!scrapedProducts.length) {
      const message = 'No scraped products to save yet. Run the scraper first.';
      setScrapeError(message);
      enqueueSnackbar(message, { variant: 'warning' });
      return;
    }

    if (!microsite) {
      const message = 'You need an active supplier microsite before saving scraped products.';
      setScrapeError(message);
      enqueueSnackbar(message, { variant: 'warning' });
      return;
    }

    setScrapeError('');
    setIsSavingScrapedProducts(true);
    try {
      await Promise.all(scrapedProducts.map((product) => persistScrapedProduct(product, microsite.id)));

      enqueueSnackbar('Scraped products saved successfully.', { variant: 'success' });
      setScrapedProducts([]);
      setSavingProductKeys([]);
      setScrapeSource('');
      router.push('/dashboard/products');
    } catch (error) {
      console.error('Failed to save scraped products', error);
      const message =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        (error instanceof Error ? error.message : undefined) ??
        'Unable to save scraped products.';
      setScrapeError(message);
      enqueueSnackbar(message, { variant: 'error' });
    } finally {
      setIsSavingScrapedProducts(false);
      setSavingProductKeys([]);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!microsite) {
      const message = 'You need an active supplier microsite before creating products.';
      setFormError(message);
      enqueueSnackbar(message, { variant: 'warning' });
      return;
    }
    if (!name.trim()) {
      setFormError('Product name is required.');
      return;
    }
    const repRowsValidation = validateProductRepFormRows(repRows);
    if (!repRowsValidation.ok) {
      setFormError(repRowsValidation.message);
      enqueueSnackbar(repRowsValidation.message, { variant: 'warning' });
      return;
    }
    setFormError('');
    setIsSubmitting(true);

    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const nextStatus =
      submitter?.value === 'PUBLISHED'
        ? 'PUBLISHED'
        : submitter?.value === 'ARCHIVED'
          ? 'ARCHIVED'
          : 'DRAFT';
    const trimmedPrice = price.trim();
    const specificationAttributes = Object.fromEntries(
      specificationRows
        .map((row) => [row.key.trim(), row.value.trim()] as const)
        .filter(([key, value]) => key.length > 0 && value.length > 0),
    );
    const variantsPayload = variantRows
      .map((row) => ({
        label: row.label.trim(),
        supplierSku: row.supplierSku.trim() || null,
        available: row.available,
        imageUrl: row.imageUrl,
      }))
      .filter((row) => row.label.length > 0 || row.supplierSku || row.imageUrl);
    const sanitizedDescription = description.trim();
    const payload = {
      micrositeId: microsite.id,
      name: name.trim(),
      shortDescription: normalizeShortDescription(shortDescription) || deriveShortDescription(sanitizedDescription) || undefined,
      description: stripHtml(sanitizedDescription).length > 0 ? sanitizedDescription : undefined,
      modelType: modelType.trim() || undefined,
      sku: sku.trim() || undefined,
      basePrice: trimmedPrice || undefined,
      currency: currency.toUpperCase(),
      stockQuantity: numberFromString(stockQuantity),
      status: nextStatus,
      isFeatured,
      primaryImageUrl: primaryMedia?.url ?? null,
      galleryImages: galleryMedia.length ? galleryMedia.map((item) => item.url) : [],
      superCategoryId: selectedSuperCategoryId || null,
      taxonomyCategoryId: selectedTaxonomyCategoryId || null,
      taxonomyClassId: selectedTaxonomyClassId || null,
      taxonomySubClassId: selectedTaxonomySubClassId || null,
      categoryId: null,
      subcategoryId: null,
      promoMessage: promoMessage.trim() ? promoMessage.trim() : 'NULL',
      variants: variantsPayload.length > 0 ? variantsPayload : undefined,
      specifications:
        Object.keys(specificationAttributes).length > 0
          ? { attributes: specificationAttributes }
          : undefined,
      representative: buildRepresentativesPayloadForApi(repRows),
    };

    try {
      await createProduct(payload);
      enqueueSnackbar('Product created successfully.', { variant: 'success' });
      router.push('/dashboard/products');
    } catch (error) {
      console.error('Failed to create product', error);
      const message =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Unable to create product. Please try again.';
      setFormError(message);
      enqueueSnackbar(message, { variant: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1088px] pb-12 pt-3 text-[#1f2c34]">
      <header className="rounded-[8px] border border-[#eceff2] bg-white px-5 py-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h1 className="text-[21px] font-semibold text-[#575757]">Add New Product</h1>
          <div className="flex w-full flex-col gap-2 sm:flex-row lg:w-auto lg:items-center">
            <div className="relative w-full lg:w-[300px]">
              <input
                value={dashboardSearch}
                onChange={(event) => setDashboardSearch(event.target.value)}
                placeholder="Search"
                className="h-[36px] w-full rounded-[4px] border border-[#b8c0c6] bg-white pl-4 pr-10 text-[14px] text-[#6a7178] outline-none"
              />
              <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#7f8790]" />
            </div>
            <button
              type="button"
              onClick={handleOpenScrapeModal}
              className="h-[36px] rounded-[4px] border border-[#c5d3d8] bg-[#f8fbfc] px-4 text-[13px] font-medium text-[#3f6771] transition hover:bg-[#edf5f7]"
            >
              Scrape Products
            </button>
          </div>
        </div>
      </header>

      {categoriesError ? (
        <div className="mt-4 rounded-[6px] border border-[#fdd4cd] bg-[#fff5f3] px-4 py-2 text-sm text-[#b6493b]">
          {categoriesError}
        </div>
      ) : null}

      {scrapeLoading ? (
        <div className="flex items-center gap-2 rounded-md border border-[#cddbe1] bg-[#f6fafb] px-4 py-2 text-sm text-[#2a7b8c]">
          <Loader2 className="h-4 w-4 animate-spin" />
          Scraping product data from the provided URL...
        </div>
      ) : null}

      {scrapeError && scrapedProducts.length === 0 ? (
        <div className="rounded-md border border-[#fdd4cd] bg-[#fff5f3] px-4 py-2 text-sm text-[#b6493b]">
          {scrapeError}
        </div>
      ) : null}

      {scrapedProducts.length > 0 ? (
        <CardSection
          title="Scraped products preview"
          description="Review scraped product data before saving it to your product list."
        >
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-[#56707a]">
                {`Fetched ${scrapedProducts.length} product${
                  scrapedProducts.length === 1 ? '' : 's'
                } from ${scrapeSourceHost || 'the selected source URL'}.`}
              </p>
              {scrapedProducts.length > 1 ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handleSaveScrapedProducts}
                    disabled={isSavingScrapedProducts || !microsite}
                    className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#226672] disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {isSavingScrapedProducts ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      'Save All'
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={clearScrapedProducts}
                    disabled={isSavingScrapedProducts}
                    className="inline-flex items-center gap-2 rounded-md border border-[#cddbe1] px-4 py-2 text-sm font-semibold text-[#4b636d] transition hover:bg-[#f1f5f6] disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    Clear
                  </button>
                </div>
              ) : null}
            </div>
            {scrapeError ? (
              <div className="rounded-md border border-[#fdd4cd] bg-[#fff5f3] px-3 py-2 text-xs text-[#b6493b]">
                {scrapeError}
              </div>
            ) : null}
            <div className="grid gap-4">
              {scrapedProducts.map((product, index) => {
                const { category: matchedCategory, subcategory: matchedSubcategory } = findMatchingCategory(
                  product.category,
                  product.subcategory,
                );
                const taxonomyPath = getTaxonomyPathFromTree(taxonomyOptions, {
                  superCategoryId: product.superCategoryId,
                  categoryId: product.taxonomyCategoryId,
                  classId: product.taxonomyClassId,
                  subClassId: product.taxonomySubClassId,
                });
                const superCategoryOptions = taxonomyOptions;
                const taxonomyCategoryOptions = taxonomyPath.superCategory?.categories ?? [];
                const visibleSubcategoryOptions = flattenVisibleSubcategoryOptions(taxonomyPath.category);
                const selectedVisibleScrapedSubcategoryId =
                  product.taxonomySubClassId ?? product.taxonomyClassId ?? '';
                const attributeEntries = Object.entries(product.attributes).filter(
                  ([, value]) => value !== null && value !== undefined && String(value).trim().length > 0,
                );
                const productKey = getScrapedProductKey(product, index);
                const isProductSaving =
                  isSavingScrapedProducts || savingProductKeys.includes(productKey);
                const normalizedDescription = (product.description || 'No description provided.').replace(/\s+/g, ' ').trim();
                const isDescriptionExpanded = expandedScrapedDescriptions.includes(productKey);
                const truncatedDescription = truncateText(normalizedDescription, 420);
                const canToggleDescription = normalizedDescription.length > truncatedDescription.length;
                return (
                  <article
                    key={`scraped-product-${index}`}
                    className="overflow-hidden rounded-lg border border-[#d7e2e7] bg-white shadow-sm"
                  >
                    <div className="grid gap-5 p-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(420px,0.9fr)]">
                      <div className="space-y-3">
                        <div className="relative h-56 w-full overflow-hidden rounded-md bg-[#f1f5f6]">
                          {product.imageUrl ? (
                            <Image
                              src={product.imageUrl}
                              alt={product.title}
                              fill
                              className="object-cover"
                              sizes="(max-width: 1280px) 100vw, 45vw"
                            />
                          ) : (
                            <div className="flex h-full items-center justify-center text-sm text-[#6a858f]">
                              No image available
                            </div>
                          )}
                        </div>
                        <div className="space-y-2">
                          <h3 className="text-[24px] font-semibold leading-tight text-[#123d4a]">
                            {product.title}
                          </h3>
                          <p className="text-[15px] leading-7 text-[#56707a]">
                            {isDescriptionExpanded ? normalizedDescription : truncatedDescription}{' '}
                            {canToggleDescription ? (
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedScrapedDescriptions((current) =>
                                    current.includes(productKey)
                                      ? current.filter((item) => item !== productKey)
                                      : [...current, productKey],
                                  )
                                }
                                className="inline font-semibold text-[#2a7b8c] hover:underline"
                              >
                                {isDescriptionExpanded ? 'View less' : 'View more'}
                              </button>
                            ) : null}
                          </p>
                        </div>
                      </div>
                      <div className="rounded-[8px] border border-[#d7e2e7] bg-[#f8fbfc] p-3">
                        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[#466974]">
                          Taxonomy
                        </p>
                        <div className="grid gap-3">
                          <label className="grid gap-1 text-xs text-[#48636c]">
                            <span className="font-semibold text-[#123d4a]">Super Category</span>
                            <select
                              value={product.superCategoryId ?? ''}
                              onChange={(event) =>
                                updateScrapedProductTaxonomy(index, 'superCategoryId', event.target.value)
                              }
                              className={FIELD_CLASSNAME}
                            >
                              <option value="">Select super category</option>
                              {superCategoryOptions.map((option) => (
                                <option key={option.id} value={option.id}>
                                  {option.name}
                                </option>
                              ))}
                            </select>
                          </label>

                          <label className="grid gap-1 text-xs text-[#48636c]">
                            <span className="font-semibold text-[#123d4a]">Category</span>
                            <select
                              value={product.taxonomyCategoryId ?? ''}
                              onChange={(event) =>
                                updateScrapedProductTaxonomy(index, 'taxonomyCategoryId', event.target.value)
                              }
                              className={FIELD_CLASSNAME}
                              disabled={!product.superCategoryId}
                            >
                              <option value="">Select category</option>
                              {taxonomyCategoryOptions.map((option) => (
                                <option key={option.id} value={option.id}>
                                  {option.name}
                                </option>
                              ))}
                            </select>
                          </label>

                          <label className="grid gap-1 text-xs text-[#48636c]">
                            <span className="font-semibold text-[#123d4a]">Subcategory</span>
                            <select
                              value={selectedVisibleScrapedSubcategoryId}
                              onChange={(event) =>
                                updateScrapedProductTaxonomy(index, 'visibleSubcategoryId', event.target.value)
                              }
                              className={FIELD_CLASSNAME}
                              disabled={!product.taxonomyCategoryId || visibleSubcategoryOptions.length === 0}
                            >
                              <option value="">
                                {visibleSubcategoryOptions.length > 0
                                  ? 'Select subcategory'
                                  : 'Products can sit directly under this category'}
                              </option>
                              {visibleSubcategoryOptions.map((option) => (
                                <option key={option.id} value={option.id}>
                                  {option.name}
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>
                        <div className="mt-3 space-y-1 text-[11px]">
                          <p className={`${matchedCategory ? 'text-[#2a7b8c]' : 'text-[#b6493b]'}`}>
                            Legacy category match: {matchedCategory?.name ?? product.category ?? 'N/A'}
                            {!matchedCategory && product.category ? ' (no match)' : null}
                          </p>
                          <p className={`${matchedSubcategory ? 'text-[#2a7b8c]' : 'text-[#b6493b]'}`}>
                            Legacy subcategory match: {matchedSubcategory?.name ?? product.subcategory ?? 'N/A'}
                            {!matchedSubcategory && product.subcategory ? ' (no match)' : null}
                          </p>
                        </div>
                      </div>
                      {attributeEntries.length > 0 ? (
                        <div className="space-y-1">
                          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#123d4a]">
                            Attributes
                          </p>
                          <dl className="overflow-hidden rounded-[8px] border border-[#d7e2e7] bg-white text-[12px] text-[#56707a]">
                            {attributeEntries.map(([key, value]) => (
                              <div
                                key={`${key}-${index}`}
                                className="grid grid-cols-[180px_minmax(0,1fr)] border-t border-[#e8eef1] first:border-t-0"
                              >
                                <dt className="bg-[#f8fbfc] px-3 py-2 font-semibold text-[#123d4a]">
                                  {formatAttributeLabel(key)}
                                </dt>
                                <dd className="px-3 py-2 text-right break-words">
                                  {attributeValueToString(value)}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </div>
                      ) : null}
                      <div className="flex flex-col gap-2 pt-2">
                        <div className="flex flex-wrap gap-3">
                          {product.productUrl ? (
                            <a
                              href={product.productUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs font-semibold text-[#2a7b8c] hover:underline"
                            >
                              View source
                            </a>
                          ) : null}
                          {product.docUrl ? (
                            <a
                              href={product.docUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs font-semibold text-[#2a7b8c] hover:underline"
                            >
                              Documentation
                            </a>
                          ) : null}
                          {product.videoUrls.length ? (
                            <span className="text-xs font-semibold text-[#56707a]">
                              {product.videoUrls.length} video{product.videoUrls.length === 1 ? '' : 's'}
                            </span>
                          ) : null}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSaveScrapedProduct(product, index)}
                          disabled={isProductSaving}
                          className="inline-flex items-center justify-center gap-2 rounded-md bg-accent px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#226672] disabled:cursor-not-allowed disabled:opacity-70"
                        >
                          {isProductSaving ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              Saving...
                            </>
                          ) : (
                            'Save Product'
                          )}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </CardSection>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-5 pt-4">
        <section className={SECTION_ACCENT_CLASSNAME}>
          <label htmlFor="product-name" className="block text-[17px] font-semibold text-[#466974]">
            Product Name: <span className="text-[#ef5a49]">*</span>
          </label>
          <input
            id="product-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Hitachi EX1900-6 Hydraulic Excavator"
            className={`mt-3 w-full ${FIELD_CLASSNAME}`}
          />
        </section>

        <section className={SECTION_CLASSNAME}>
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-[17px] font-semibold text-[#466974]">
              Product Image: <span className="text-[#ef5a49]">*</span>
            </h2>
            <span className="text-[13px] text-[#9aa4ab]">(Maximum {MAX_GALLERY_IMAGES} Images)</span>
          </div>
          <div className="mt-4 rounded-[4px] bg-[#f3fcfc] px-4 py-3">
            <div className="flex flex-wrap gap-3">
              {mediaStripItems.map((item, index) => {
                const isSelected = primaryMedia?.url === item.url;
                return (
                  <div key={item.url} className="w-[78px]">
                    <div className="relative h-[58px] overflow-hidden border border-[#cad3d8] bg-white">
                      <Image src={item.url} alt={`Image ${index + 1}`} fill className="object-cover" unoptimized />
                      {index !== 0 ? (
                        <button
                          type="button"
                          onClick={() => removeGalleryImage(item.url)}
                          className="absolute right-1 top-1 inline-flex h-5 w-5 items-center justify-center rounded-full bg-white/95 text-[#566971]"
                          aria-label={`Remove image ${index + 1}`}
                        >
                          <X size={12} />
                        </button>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSelectPrimaryImage(item.url)}
                      className="mt-1 inline-flex items-center gap-1 text-[12px] text-[#8a949b]"
                    >
                      <span className={`h-[11px] w-[11px] rounded-full border ${isSelected ? 'border-[#4a6f79] bg-[#4a6f79]' : 'border-[#b7c0c7] bg-white'}`} />
                      {`Image ${index + 1}`}
                    </button>
                  </div>
                );
              })}
              {mediaStripItems.length < MAX_GALLERY_IMAGES ? (
                <button
                  type="button"
                  onClick={() => galleryInputRef.current?.click()}
                  className="flex h-[58px] w-[58px] items-center justify-center border border-dashed border-[#b8c3c8] bg-white text-[#90979e]"
                >
                  <ImagePlus className="h-6 w-6" />
                </button>
              ) : null}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => openMediaModal('gallery')}
              className="rounded-[4px] border border-[#bfd0d6] bg-white px-3 py-2 text-[13px] font-medium text-[#486a74]"
            >
              Browse Library
            </button>
            <button
              type="button"
              onClick={() => galleryInputRef.current?.click()}
              disabled={galleryUploading}
              className="inline-flex items-center gap-2 rounded-[4px] border border-[#bfd0d6] bg-white px-3 py-2 text-[13px] font-medium text-[#486a74] disabled:opacity-60"
            >
              {galleryUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              Upload Images
            </button>
            <input
              ref={galleryInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={handleGalleryUpload}
              className="hidden"
            />
          </div>

          <div className="mt-4 flex flex-wrap items-baseline gap-2">
            <h3 className="text-[16px] font-semibold text-[#466974]">
              Select Main Product Image: <span className="text-[#ef5a49]">*</span>
            </h3>
            <span className="text-[13px] text-[#9aa4ab]">(1 Image only)</span>
          </div>
          <div className="mt-3 flex min-h-[74px] items-center gap-3 rounded-[4px] border border-[#bcc6cc] bg-white px-4 py-2">
            {primaryMedia ? (
              <div className="relative h-[58px] w-[95px] overflow-hidden border border-[#c6d0d5]">
                <Image src={primaryMedia.url} alt="Primary product" fill className="object-cover" unoptimized />
                <button
                  type="button"
                  onClick={removePrimaryImage}
                  className="absolute right-1 top-1 inline-flex h-5 w-5 items-center justify-center rounded-full bg-white/95 text-[#566971]"
                  aria-label="Remove primary image"
                >
                  <X size={12} />
                </button>
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => primaryInputRef.current?.click()}
              disabled={primaryUploading}
              className="flex h-[58px] w-[58px] items-center justify-center border border-dashed border-[#b8c3c8] bg-white text-[#90979e] disabled:opacity-60"
            >
              {primaryUploading ? <Loader2 className="h-5 w-5 animate-spin" /> : <ImagePlus className="h-6 w-6" />}
            </button>
            <button
              type="button"
              onClick={() => openMediaModal('primary')}
              className="rounded-[4px] border border-[#bfd0d6] bg-[#f8fbfc] px-3 py-2 text-[13px] font-medium text-[#486a74]"
            >
              Browse Library
            </button>
            <input
              ref={primaryInputRef}
              type="file"
              accept="image/*"
              onChange={handlePrimaryUpload}
              className="hidden"
            />
          </div>
        </section>

        <section className={SECTION_CLASSNAME}>
          <label className="block text-[17px] font-semibold text-[#466974]">
            Model Type <span className="text-[#ef5a49]">*</span>
          </label>
          <input
            value={modelType}
            onChange={(event) => setModelType(event.target.value)}
            placeholder="EX1900-6"
            className={`mt-3 w-full max-w-[540px] ${FIELD_CLASSNAME}`}
          />
        </section>

        <section className={SECTION_CLASSNAME}>
          <label className="block text-[17px] font-semibold text-[#466974]">
            Short Description
          </label>
          <textarea
            value={shortDescription}
            onChange={(event) => setShortDescription(event.target.value)}
            placeholder="Brief product summary shown on product cards and search results."
            rows={4}
            className="mt-3 min-h-[112px] w-full resize-y rounded-[4px] border border-[#b6c0c6] bg-white px-4 py-3 text-[15px] leading-6 text-[#48636c] outline-none transition focus:border-[#62808a] focus:ring-0"
          />
        </section>

        <section className={SECTION_CLASSNAME}>
          <label className="block text-[17px] font-semibold text-[#466974]">
            Product Description: <span className="text-[#ef5a49]">*</span>
          </label>
          <div className="mt-3 overflow-hidden rounded-[4px] border border-[#d3d9de] bg-white">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#e5eaee] px-4 py-2 text-[13px] text-[#6a767d]">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => runDescriptionCommand('formatBlock', '<p>')}
                  className="rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] text-[#6c757c]"
                >
                  P
                </button>
                <button
                  type="button"
                  onClick={() => runDescriptionCommand('bold')}
                  className="rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] font-semibold text-[#54707a]"
                >
                  B
                </button>
                <button
                  type="button"
                  onClick={() => runDescriptionCommand('insertUnorderedList')}
                  className="rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] text-[#54707a]"
                >
                  List
                </button>
                <button
                  type="button"
                  onClick={() => runDescriptionCommand('justifyLeft')}
                  className="rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] text-[#54707a]"
                >
                  Align
                </button>
                <button
                  type="button"
                  onClick={() => runDescriptionCommand('outdent')}
                  className="rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] text-[#54707a]"
                >
                  Outdent
                </button>
                <button
                  type="button"
                  onClick={() => runDescriptionCommand('indent')}
                  className="rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] text-[#54707a]"
                >
                  Indent
                </button>
                <button
                  type="button"
                  onClick={handleInsertDescriptionImage}
                  className="rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] text-[#54707a]"
                >
                  Image
                </button>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsDescriptionHtmlMode((current) => !current)}
                  className={`rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] ${
                    isDescriptionHtmlMode ? 'bg-[#eef5f7] text-[#355c67]' : 'text-[#54707a]'
                  }`}
                >
                  {isDescriptionHtmlMode ? 'Exit HTML Mode' : 'Try NEW Advanced Mode'}
                </button>
                <button
                  type="button"
                  onClick={() => setIsDescriptionPreview((current) => !current)}
                  className={`rounded-[4px] border border-[#d6dde1] px-2 py-1 text-[12px] ${
                    isDescriptionPreview ? 'bg-[#eef5f7] text-[#355c67]' : 'text-[#6c757c]'
                  }`}
                >
                  {isDescriptionPreview ? 'Edit' : 'Preview'}
                </button>
              </div>
            </div>
            {isDescriptionHtmlMode ? (
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={10}
                placeholder="<p>Describe the product, capabilities, site fit, and use cases.</p>"
                className="min-h-[220px] w-full resize-y border-0 px-4 py-4 font-mono text-[13px] leading-7 text-[#506670] outline-none"
              />
            ) : isDescriptionPreview ? (
              <div
                className="min-h-[220px] px-4 py-4 text-[15px] leading-8 text-[#506670] [&_img]:my-3 [&_img]:max-h-[220px] [&_img]:max-w-full [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-6"
                dangerouslySetInnerHTML={{
                  __html:
                    description ||
                    '<p class="text-[#9ca3af]">Describe the product, capabilities, site fit, and use cases.</p>',
                }}
              />
            ) : (
              <div className="relative">
                {!descriptionPlainText ? (
                  <span className="pointer-events-none absolute left-4 top-4 text-[15px] text-[#9ca3af]">
                    Describe the product, capabilities, site fit, and use cases.
                  </span>
                ) : null}
                <div
                  ref={descriptionEditorRef}
                  contentEditable
                  suppressContentEditableWarning
                  onInput={handleDescriptionInput}
                  className="min-h-[220px] px-4 py-4 text-[15px] leading-8 text-[#506670] outline-none [&_img]:my-3 [&_img]:max-h-[220px] [&_img]:max-w-full [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-6"
                />
              </div>
            )}
          </div>
        </section>

        <section className={SECTION_CLASSNAME}>
          <label className="block text-[17px] font-semibold text-[#466974]">
            Price, Stock & Variants <span className="text-[#ef5a49]">*</span>
          </label>
          <div className="mt-3 overflow-hidden rounded-[4px] border border-[#bcc7cc] bg-white">
            <table className="w-full border-collapse text-left text-[14px] text-[#4a6570]">
              <thead>
                <tr className="bg-[#eff8f8] text-center text-[14px] font-semibold text-[#4b6771]">
                  <th className="border-r border-[#bcc7cc] px-4 py-3">Variant</th>
                  <th className="border-r border-[#bcc7cc] px-4 py-3">Supplier SKU</th>
                  <th className="px-4 py-3">Availability</th>
                </tr>
              </thead>
              <tbody>
                {variantRows.map((row) => (
                  <tr key={row.id} className="border-t border-[#bcc7cc]">
                    <td className="border-r border-[#bcc7cc] px-4 py-4">
                      <div className="flex items-start gap-4">
                        <div className="relative h-[42px] w-[56px] overflow-hidden border border-[#ccd4d9] bg-[#f5f8f9]">
                          {row.imageUrl ? (
                            <Image src={row.imageUrl} alt={row.label} fill className="object-cover" unoptimized />
                          ) : (
                            <div className="flex h-full items-center justify-center text-[11px] text-[#93a0a7]">No image</div>
                          )}
                        </div>
                        <div className="min-w-0 flex-1 space-y-2">
                          <input
                            value={row.label}
                            onChange={(event) => handleVariantLabelChange(row.id, event.target.value)}
                            placeholder="Variant name"
                            className="h-[34px] w-full rounded-[4px] border border-[#bac4ca] px-3 text-[14px] text-[#4c6670] outline-none"
                          />
                          <select
                            value={row.imageUrl ?? ''}
                            onChange={(event) => handleVariantImageChange(row.id, event.target.value)}
                            className="h-[34px] w-full rounded-[4px] border border-[#bac4ca] bg-white px-3 text-[13px] text-[#4c6670] outline-none"
                          >
                            <option value="">Select image</option>
                            {mediaStripItems.map((item, index) => (
                              <option key={`${row.id}-${item.url}`} value={item.url}>
                                {`Image ${index + 1}`}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </td>
                    <td className="border-r border-[#bcc7cc] px-4 py-4">
                      <div className="flex max-w-[260px] items-center rounded-[4px] border border-[#bac4ca] bg-white px-3">
                        <input
                          value={row.supplierSku}
                          onChange={(event) => handleVariantSkuChange(row.id, event.target.value)}
                          placeholder={`Customized-SKU-${row.label.slice(-1)}`}
                          className="h-[34px] flex-1 border-0 bg-transparent text-[14px] text-[#4c6670] outline-none"
                        />
                        <span className="text-[12px] text-[#6b7881]">{`${row.supplierSku.length}/200`}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-center gap-3">
                        <button
                          type="button"
                          onClick={() => handleVariantAvailabilityChange(row.id)}
                          className={`relative h-[28px] w-[46px] rounded-full transition ${row.available ? 'bg-[#4e6972]' : 'bg-[#a8adb0]'}`}
                          aria-label={`Toggle availability for ${row.label}`}
                        >
                          <span
                            className={`absolute top-[4px] h-[20px] w-[20px] rounded-full bg-white transition ${row.available ? 'left-[22px]' : 'left-[4px]'}`}
                          />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRemoveVariantRow(row.id)}
                          disabled={variantRows.length === 1}
                          className="inline-flex h-[34px] w-[34px] items-center justify-center rounded-[4px] border border-[#d5dde1] text-[#7d8a92] disabled:cursor-not-allowed disabled:opacity-40"
                          aria-label={`Remove ${row.label || 'variant'}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            type="button"
            onClick={handleAddVariantRow}
            className="mt-3 inline-flex items-center gap-2 rounded-[4px] border border-[#bfd0d6] bg-[#f8fbfc] px-3 py-2 text-[13px] font-medium text-[#486a74]"
          >
            <Plus className="h-4 w-4" />
            Add Variant
          </button>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <label className="flex flex-col gap-2 text-[15px] font-semibold text-[#466974]">
              Price
              <input value={price} onChange={(event) => setPrice(event.target.value)} placeholder="500000" inputMode="decimal" className={FIELD_CLASSNAME} />
            </label>
            <label className="flex flex-col gap-2 text-[15px] font-semibold text-[#466974]">
              Currency
              <select value={currency} onChange={(event) => setCurrency(event.target.value as (typeof CURRENCY_OPTIONS)[number])} className={FIELD_CLASSNAME}>
                {CURRENCY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-[15px] font-semibold text-[#466974]">
              Stock
              <input value={stockQuantity} onChange={(event) => setStockQuantity(event.target.value)} placeholder="10" inputMode="numeric" className={FIELD_CLASSNAME} />
            </label>
          </div>
        </section>
        <section className={SECTION_CLASSNAME}>
          <div>
            <h2 className="text-[17px] font-semibold text-[#466974]">Product Specification</h2>
            <p className="mt-1 text-[13px] text-[#9aa4ab]">
              Fill more product specification will increase product searchability
            </p>
          </div>
          {suggestedSpecificationKeys.length > 0 ? (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-medium text-[#7f9098]">Suggested fields:</span>
              {suggestedSpecificationKeys.map((field) => (
                <button
                  key={field}
                  type="button"
                  onClick={() => handleAddSpecificationRow(field)}
                  className="rounded-full border border-[#d4dce0] bg-[#f8fbfc] px-3 py-1 text-[12px] text-[#55707a]"
                >
                  {field}
                </button>
              ))}
            </div>
          ) : null}
          <div className="mt-4 space-y-3">
            {specificationRows.length === 0 ? (
              <div className="rounded-[4px] border border-dashed border-[#cfd8dc] px-4 py-4 text-[14px] text-[#8a979d]">
                Select a category or add custom specifications.
              </div>
            ) : null}
            {specificationRows.map((row) => (
              <div key={row.id} className="grid gap-3 md:grid-cols-[minmax(0,240px)_minmax(0,1fr)_44px]">
                <input
                  value={row.key}
                  onChange={(event) => handleSpecificationChange(row.id, 'key', event.target.value)}
                  placeholder="Specification name"
                  className={FIELD_CLASSNAME}
                />
                <input
                  value={row.value}
                  onChange={(event) => handleSpecificationChange(row.id, 'value', event.target.value)}
                  placeholder="Specification value"
                  className={FIELD_CLASSNAME}
                />
                <button
                  type="button"
                  onClick={() => handleRemoveSpecificationRow(row.id)}
                  className="inline-flex h-[42px] items-center justify-center rounded-[4px] border border-[#d5dde1] text-[#7d8a92]"
                  aria-label={`Remove ${row.key || 'specification'}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => handleAddSpecificationRow()}
            className="mt-3 inline-flex items-center gap-2 rounded-[4px] border border-[#bfd0d6] bg-[#f8fbfc] px-3 py-2 text-[13px] font-medium text-[#486a74]"
          >
            <Plus className="h-4 w-4" />
            Add Specification
          </button>
        </section>

        <section className={SECTION_CLASSNAME}>
          <div>
            <h2 className="text-[17px] font-semibold text-[#466974]">Product representatives</h2>
            <p className="mt-1 text-[13px] text-[#9aa4ab]">
              Add up to {MAX_PRODUCT_REPRESENTATIVES} representatives for FAQs, quote requests, and ViewRoom
              invitations.
            </p>
            <div className="mt-4 space-y-8">
              {repRows.map((row, rowIndex) => (
                <div
                  key={row.id}
                  className="rounded-lg border border-[#e2ecef] bg-[#fafcfd] px-4 py-4 sm:px-5 sm:py-5"
                >
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[14px] font-semibold text-[#466974]">Representative {rowIndex + 1}</p>
                    {repRows.length > 1 ? (
                      <button
                        type="button"
                        onClick={() =>
                          setRepRows((prev) =>
                            prev.length > 1 ? prev.filter((_, i) => i !== rowIndex) : prev,
                          )
                        }
                        className="text-[13px] font-medium text-red-600 hover:text-red-700"
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                  <ProductRepresentativeFields
                    intro={
                      rowIndex === 0
                        ? 'Name contacts who will handle FAQs, Request for Quote and ViewRoom invitations for this product.'
                        : ''
                    }
                    repName={row.name}
                    setRepName={(v) =>
                      setRepRows((prev) =>
                        prev.map((r, i) => (i === rowIndex ? { ...r, name: v } : r)),
                      )
                    }
                    repEmail={row.email}
                    setRepEmail={(v) =>
                      setRepRows((prev) =>
                        prev.map((r, i) => (i === rowIndex ? { ...r, email: v } : r)),
                      )
                    }
                    repMobile={row.mobile}
                    setRepMobile={(v) =>
                      setRepRows((prev) =>
                        prev.map((r, i) => (i === rowIndex ? { ...r, mobile: v } : r)),
                      )
                    }
                    repImageMedia={row.imageMedia}
                    repImageUploading={repImageUploadingIndex === rowIndex}
                    onRemoveRepImage={() =>
                      setRepRows((prev) =>
                        prev.map((r, i) => (i === rowIndex ? { ...r, imageMedia: null } : r)),
                      )
                    }
                    onBrowseRepresentativeLibrary={() => {
                      repMediaRowIndexRef.current = rowIndex;
                      openMediaModal('representative');
                    }}
                    onUploadClick={() => {
                      repMediaRowIndexRef.current = rowIndex;
                      repImageInputRef.current?.click();
                    }}
                    repAvailability={row.availability}
                    setRepAvailability={(next) =>
                      setRepRows((prev) =>
                        prev.map((r, i) => {
                          if (i !== rowIndex) return r;
                          const availability =
                            typeof next === 'function' ? next(r.availability) : next;
                          return { ...r, availability };
                        }),
                      )
                    }
                    onClearAll={() =>
                      setRepRows((prev) =>
                        prev.map((r, i) =>
                          i === rowIndex ? { ...createEmptyProductRepFormRow(), id: r.id } : r,
                        ),
                      )
                    }
                    showClearButton
                  />
                </div>
              ))}
            </div>
            <input
              ref={repImageInputRef}
              type="file"
              accept="image/*"
              onChange={handleRepImageUpload}
              className="hidden"
            />
            {repRows.length < MAX_PRODUCT_REPRESENTATIVES ? (
              <button
                type="button"
                onClick={() => setRepRows((prev) => [...prev, createEmptyProductRepFormRow()])}
                className="mt-6 inline-flex items-center gap-2 rounded-[4px] border border-[#4e737e] bg-white px-4 py-2 text-[13px] font-semibold text-[#4e737e] transition hover:bg-[#edf5f7]"
              >
                <Plus className="h-4 w-4" />
                Add another representative
              </button>
            ) : null}
          </div>
        </section>

        <section className={SECTION_CLASSNAME}>
          <div>
            <h2 className="text-[17px] font-semibold text-[#466974]">Product Taxonomy</h2>
            <p className="mt-1 text-[13px] text-[#9aa4ab]">
              Platform-controlled taxonomy path: super category, category, and optional subcategory.
              Suppliers do not define taxonomy names. Specification suggestions update from the selected path.
            </p>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="product-super-category" className="block text-[15px] font-semibold text-[#466974]">
                Super Category <span className="text-[#ef5a49]">*</span>
              </label>
              <select
                id="product-super-category"
                value={selectedSuperCategoryId}
                onChange={(event) => setSelectedSuperCategoryId(event.target.value)}
                disabled={categoriesLoading || taxonomyOptions.length === 0}
                className={`w-full ${FIELD_CLASSNAME}`}
              >
                <option value="">
                  {categoriesLoading ? 'Loading taxonomy...' : 'Select super category'}
                </option>
                {taxonomyOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label htmlFor="product-taxonomy-category" className="block text-[15px] font-semibold text-[#466974]">
                Category <span className="text-[#ef5a49]">*</span>
              </label>
              <select
                id="product-taxonomy-category"
                value={selectedTaxonomyCategoryId}
                onChange={(event) => setSelectedTaxonomyCategoryId(event.target.value)}
                disabled={categoriesLoading || taxonomyCategoryOptions.length === 0}
                className={`w-full ${FIELD_CLASSNAME}`}
              >
                <option value="">
                  {selectedSuperCategoryId ? 'Select category' : 'Choose super category first'}
                </option>
                {taxonomyCategoryOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label htmlFor="product-taxonomy-subclass" className="block text-[15px] font-semibold text-[#466974]">
                Subcategory
              </label>
              <select
                id="product-taxonomy-subclass"
                value={selectedVisibleSubcategoryId}
                onChange={(event) => applyVisibleSubcategorySelection(event.target.value, selectedTaxonomyCategory)}
                disabled={categoriesLoading || !selectedTaxonomyCategoryId || visibleSubcategoryOptions.length === 0}
                className={`w-full ${FIELD_CLASSNAME}`}
              >
                <option value="">
                  {selectedTaxonomyCategoryId
                    ? visibleSubcategoryOptions.length > 0
                      ? 'Select subcategory'
                      : 'Products can sit directly under this category'
                    : 'Choose category first'}
                </option>
                {visibleSubcategoryOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="mt-3 text-[13px] text-[#8d989e]">
            If you didn&apos;t find the right taxonomy, recommend the missing super category,
            category, or subcategory. Final taxonomy naming and placement stays under platform control.
          </p>
          <button
            type="button"
            onClick={() => router.push('/dashboard/products/categories')}
            className="mt-1 text-[14px] font-medium text-[#6b6cff] underline underline-offset-2"
          >
            Recommend Product Categories
          </button>
        </section>

        {formError ? (
          <div className="rounded-md border border-[#fdd4cd] bg-[#fff5f3] px-4 py-3 text-sm text-[#b6493b]">
            {formError}
          </div>
        ) : null}

        <div className="flex flex-col gap-3 pb-4 pt-2 md:flex-row md:justify-end">
          <button
            type="button"
            onClick={() => router.push('/dashboard/products')}
            className="rounded-[4px] border border-[#7d99a4] bg-white px-6 py-2.5 text-sm font-semibold text-[#4b636d] transition hover:bg-[#f1f5f6]"
          >
            Cancel
          </button>
          <button
            type="submit"
            value="DRAFT"
            disabled={isSubmitting || !name.trim() || !microsite}
            className="rounded-[4px] border border-[#7d99a4] bg-white px-6 py-2.5 text-sm font-semibold text-[#4b636d] transition hover:bg-[#f1f5f6] disabled:cursor-not-allowed disabled:opacity-70"
          >
            Save as draft
          </button>
          <button
            type="submit"
            value="PUBLISHED"
            disabled={isSubmitting || !name.trim() || !microsite}
            className="rounded-[4px] bg-[#4e737e] px-7 py-2.5 text-sm font-semibold text-white transition hover:bg-[#3f636e] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isSubmitting ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </form>

      <MediaModal
        isOpen={mediaModalTarget !== null}
        onClose={() => setMediaModalTarget(null)}
        onInsert={handleMediaInsert}
      />

      {isScrapeModalOpen ? (
        <div
          className="fixed inset-0 mt-0 z-50 flex items-center justify-center bg-black/40 px-4"
          onClick={handleCloseScrapeModal}
        >
          <div
            className="max-h-[min(90vh,880px)] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-[#123d4a]">Scrape Products</h2>
                <p className="mt-1 text-sm text-[#56707a]">
                  Paste the product URL you want to scrape. We&apos;ll fetch the product and show it
                  below so you can save it to your catalogue. Representative details you add here are
                  saved with the product as soon as you save the scrape.
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseScrapeModal}
                disabled={scrapeLoading}
                className="rounded-full p-1 text-[#4b636d] transition hover:bg-[#f1f5f6] disabled:opacity-60"
                aria-label="Close scrape modal"
              >
                <X size={18} />
              </button>
            </div>
            <div className="mt-5 space-y-2">
              <label className="flex flex-col gap-2 text-sm font-medium text-[#123d4a]">
                Product URL
                <input
                  value={scrapeUrl}
                  onChange={(event) => {
                    setScrapeUrl(event.target.value);
                    if (scrapeUrlError) setScrapeUrlError('');
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      void handleScrapeSubmit();
                    }
                  }}
                  placeholder="https://example.com/product/example-item"
                  autoFocus
                  disabled={scrapeLoading}
                  className="rounded-md border border-[#cddbe1] px-3 py-2 text-sm outline-none transition focus:border-[#2a7b8c] focus:ring-2 focus:ring-[#2a7b8c]/20 disabled:cursor-not-allowed disabled:bg-[#f1f5f6]"
                />
              </label>
              {scrapeUrlError ? (
                <p className="text-sm text-[#b6493b]">{scrapeUrlError}</p>
              ) : null}
            </div>

            <div className="mt-6 border-t border-[#e8eef1] pt-5">
              <h3 className="text-[15px] font-semibold text-[#466974]">Product representatives</h3>
              <p className="mt-2 text-sm text-[#56707a]">
                Contacts in the Product representatives section on this page are included when you save a scraped
                product (up to {MAX_PRODUCT_REPRESENTATIVES} representatives).
              </p>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={handleCloseScrapeModal}
                disabled={scrapeLoading}
                className="rounded-md border border-[#cddbe1] px-4 py-2 text-sm font-semibold text-[#4b636d] transition hover:bg-[#f1f5f6] disabled:cursor-not-allowed disabled:opacity-70"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleScrapeSubmit}
                disabled={scrapeLoading}
                className="inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#226672] disabled:cursor-not-allowed disabled:opacity-70"
              >
                {scrapeLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Scraping...
                  </>
                ) : (
                  'Scrape'
                )}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

