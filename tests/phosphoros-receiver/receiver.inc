/* Isolated original-GIF output receiver timing; input packets are diagnostic
   fixtures, standing in for the FPGA's decoded cart-SDRAM output. */
static void gif_span_bench(const char *args)
{
    enum { PX = 320 * 240, PACKET_MAX = 32 + 960 + PX };
    char path[192];
    snprintf(path, sizeof path, "%s/gif-span-fixture.bin", path_get("data"));
    phos_cart_key_t key;
    if (!phos_cart_key_init(&key, path, 0x47534231u)) {
        phos_log("[gifspan] fail reason=file\n");
        return;
    }
    while (!phos_cart_cache_read_poll()) { }
    phos_cart_blob_t blob = phos_cart_cache_stage_asset(&key, path);
    uint32_t hd[4] __attribute__((aligned(16)));
    uint32_t ent[16] __attribute__((aligned(16)));
    unsigned which = (unsigned)strtoul(args, NULL, 10);
    if (!blob || !phos_cart_cache_read(blob, 0, hd, sizeof hd) ||
        hd[0] != 0x47534231u || !hd[1] || hd[1] > 32 ||
        which >= hd[1] || hd[2] != 528 || hd[3] != key.size ||
        !phos_cart_cache_read(blob, hd[2] + which * 64, ent, sizeof ent) ||
        ent[5] < 192 || ent[5] > PACKET_MAX || (ent[5] & 15) ||
        ent[6] > 1200 || ent[5] != 192 + ent[6] * 64 ||
        ent[2] > key.size || PX > key.size - ent[2] ||
        ent[3] > key.size || PX > key.size - ent[3] ||
        ent[4] > key.size || ent[5] > key.size - ent[4] ||
        ent[10] < 992 || ent[10] > PACKET_MAX || (ent[10] & 15) ||
        ent[11] > 240 || ent[12] > PX ||
        ent[10] != ((992 + ent[12] + 15) & ~15u) ||
        ent[9] > key.size || ent[10] > key.size - ent[9]) {
        phos_log("[gifspan] fail reason=header\n");
        return;
    }
    uint8_t *plane = memalign(64, PX + 64);
    uint8_t *packet = memalign(64, PACKET_MAX + 64);
    uint16_t *rgb = memalign(64, PX * 2);
    uint16_t *pal = memalign(16, 512);
    if (!plane || !packet || !rgb || !pal) {
        phos_log("[gifspan] fail reason=alloc\n");
        goto done;
    }
    if (!phos_cart_cache_read(blob, 16, pal, 512)) {
        phos_log("[gifspan] fail reason=palette\n");
        goto done;
    }
    data_cache_hit_writeback(pal, 512);
    data_cache_hit_writeback_invalidate(rgb, PX * 2);
    rspq_wait();
    phos_img_t img = { .s = surface_make_linear(plane, FMT_CI8, 320, 240),
                       .tlut = pal, .cached = true };
    surface_t target = surface_make_linear(rgb, FMT_RGBA16, 320, 240);
    phos_blit_opts_t opts = { .alpha = 255, .fast_copy = true };
    for (unsigned rep = 0; rep < 5; rep++) {
        uint32_t render_hash[3] = {0};
        for (unsigned kind = 0; kind < 3; kind++) {
            sound_topup();
            memset(plane + PX, 0xA5, 64);
            memset(packet + PACKET_MAX, 0xA5, 64);
            if (kind && !phos_cart_cache_read(blob, ent[2], plane, PX)) {
                phos_log("[gifspan] fail reason=reference\n");
                goto done;
            }
            uint32_t wire_off = kind == 2 ? ent[9] : kind ? ent[4] : ent[3];
            uint32_t wire_len = kind == 2 ? ent[10] : kind ? ent[5] : PX;
            uint64_t start = phos_now_us();
            bool ok = phos_cart_cache_read(blob, wire_off,
                                           kind ? packet : plane,
                                           wire_len);
            uint32_t pi_us = (uint32_t)(phos_now_us() - start);
            if (!ok) {
                phos_log("[gifspan] fail reason=read\n");
                goto done;
            }
            start = phos_now_us();
            if (kind) {
                uint32_t *p = (uint32_t *)packet;
                if (p[0] != (kind == 2 ? 0x47505231u : 0x47504431u) || p[1] != 1 || p[2] != ent[0] ||
                    p[3] != ent[1] || p[4] != ((320u << 16) | 240u) ||
                    p[5] != kind ||
                    p[6] != (kind == 2 ? ent[11] : ent[6]) ||
                    p[7] != (kind == 2 ? ent[12] : ent[6] * 64)) {
                    phos_log("[gifspan] fail reason=packet\n");
                    goto done;
                }
                if (kind == 2) {
                    uint16_t *rows = (uint16_t *)(packet + 32);
                    uint32_t count = 0, consumed = 0;
                    for (unsigned y = 0; y < 240; y++) {
                        unsigned x = rows[y * 2], n = rows[y * 2 + 1];
                        if (!n) {
                            if (x) {
                                phos_log("[gifspan] fail reason=empty_row\n");
                                goto done;
                            }
                            continue;
                        }
                        if (x >= 320 || n > 320 - x || ((x | n) & 7) ||
                            n > ent[12] - consumed) {
                            phos_log("[gifspan] fail reason=row_bounds\n");
                            goto done;
                        }
                        memcpy(plane + y * 320 + x, packet + 992 + consumed, n);
                        consumed += n;
                        count++;
                    }
                    if (count != ent[11] || consumed != ent[12]) {
                        phos_log("[gifspan] fail reason=row_count\n");
                        goto done;
                    }
                } else {
                    uint32_t count = 0;
                    for (unsigned tile = 0; tile < 1200; tile++) {
                        if (!(packet[32 + tile / 8] & (1u << (tile % 8)))) continue;
                        if (count >= ent[6]) {
                            phos_log("[gifspan] fail reason=mask\n");
                            goto done;
                        }
                        unsigned x = (tile % 40) * 8, y = (tile / 40) * 8;
                        for (unsigned row = 0; row < 8; row++)
                            memcpy(plane + (y + row) * 320 + x,
                                   packet + 192 + count * 64 + row * 8, 8);
                        count++;
                    }
                    if (count != ent[6]) {
                        phos_log("[gifspan] fail reason=count\n");
                        goto done;
                    }
                }
                data_cache_hit_writeback(plane, PX);
            }
            uint32_t apply_us = (uint32_t)(phos_now_us() - start);
            if (phos_crc32(plane, PX) != ent[7]) {
                phos_log("[gifspan] fail reason=output\n");
                goto done;
            }
            for (unsigned j = 0; j < 64; j++) {
                if (plane[PX + j] != 0xA5 || packet[PACKET_MAX + j] != 0xA5) {
                    phos_log("[gifspan] fail reason=guard\n");
                    goto done;
                }
            }
            start = phos_now_us();
            rdpq_attach_clear(&target, NULL);
            gpu_blit(&img, 0, 0, &opts);
            rdpq_detach_wait();
            uint32_t rdp_us = (uint32_t)(phos_now_us() - start);
            data_cache_hit_invalidate(rgb, PX * 2);
            render_hash[kind] = phos_crc32(rgb, PX * 2);
            if (render_hash[kind] != ent[8]) {
                phos_log("[gifspan] fail reason=golden_render got=%08lx expected=%08lx\n",
                         (unsigned long)render_hash[kind], (unsigned long)ent[8]);
                goto done;
            }
            phos_log("[gifspan] case=%u frame=%lu rep=%u mode=%s bytes=%lu tiles=%lu pi_us=%lu apply_us=%lu rdp_us=%lu crc=%08lx\n",
                     which, (unsigned long)ent[0], rep, kind == 2 ? "spans" : kind ? "tiles" : "full",
                     (unsigned long)wire_len, (unsigned long)ent[6],
                     (unsigned long)pi_us, (unsigned long)apply_us,
                     (unsigned long)rdp_us, (unsigned long)render_hash[kind]);
        }
        if (render_hash[0] != render_hash[1] || render_hash[0] != render_hash[2]) {
            phos_log("[gifspan] fail reason=render\n");
            goto done;
        }
    }
    phos_log("[gifspan] PASS case=%u repeats=5\n", which);
done:
    rspq_wait();
    free(pal);
    free(rgb);
    free(packet);
    free(plane);
}
