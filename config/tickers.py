"""
config/tickers.py
Quản lý danh mục mã cổ phiếu, phân nhóm 9 ngành ICB, nhóm đặc thù (Vingroup, Tài chính, CTCK)
và danh mục tài sản vĩ mô / hàng hóa quốc tế.
"""

# 4 mã thuộc hệ sinh thái Vingroup niêm yết HOSE
VINGROUP_TICKERS = ['VIC', 'VHM', 'VRE', 'VPL']

# Danh sách CTCK niêm yết chuẩn năm 2026 (bao gồm mã đã niêm yết mới như VCK, TCX, VPX)
SECURITIES_TICKERS = [
    'SSI', 'VCK', 'TCX', 'VPX', 'HCM', 'VCI', 'VND', 'MBS', 'VIX',
    'CTS', 'BSI', 'FTS', 'SHS', 'ORS', 'AGR', 'BVS'
]

# Phân nhóm 9 ngành chính của thị trường chứng khoán Việt Nam
SECTOR_MAPPING = {
    "Ngân hàng": [
        'VCB', 'BID', 'CTG', 'TCB', 'MBB', 'ACB', 'VPB', 'HDB', 'STB',
        'LPB', 'VIB', 'SHB', 'TPB', 'MSB', 'OCB', 'EIB', 'SSB', 'BAB'
    ],
    "Chứng khoán": SECURITIES_TICKERS,
    "Bất động sản": [
        'VIC', 'VHM', 'VRE', 'VPL', 'NVL', 'KDH', 'NLG', 'DXG', 'PDR',
        'DIG', 'CEO', 'HDG', 'KBC', 'IDC', 'BCM', 'SZC', 'TCH', 'DXS',
        'VPI', 'CRE'
    ],
    "Thép & VLXD": [
        'HPG', 'HSG', 'NKG', 'VGS', 'HT1', 'BCC', 'POM', 'SMC', 'TLH'
    ],
    "Dầu khí & Năng lượng": [
        'GAS', 'PVD', 'PVS', 'PVT', 'PLX', 'BSR', 'OIL', 'PVC', 'PVP'
    ],
    "Bán lẻ & Tiêu dùng": [
        'MWG', 'FRT', 'DGW', 'MSN', 'VNM', 'SAB', 'PNJ', 'KDC', 'SBT',
        'DBC', 'BAF', 'HAX', 'PET'
    ],
    "Công nghệ & Viễn thông": [
        'FPT', 'CMG', 'ELC', 'SAM', 'FOX', 'CTR', 'VGI'
    ],
    "Điện, Nước & Tiện ích": [
        'POW', 'GEG', 'PC1', 'REE', 'NT2', 'VSH', 'BWE', 'TDM', 'PPC', 'HND'
    ],
    "Đầu tư công & Xây dựng": [
        'VCG', 'HHV', 'LCG', 'C4G', 'FCN', 'KSB', 'DHA', 'CTD', 'HBC'
    ]
}

# Nhóm Tài chính (Ngân hàng, Chứng khoán, Bảo hiểm) miễn trừ điều kiện Nợ/VCSH < 1.2
FINANCIAL_TICKERS = set(
    SECTOR_MAPPING["Ngân hàng"] +
    SECTOR_MAPPING["Chứng khoán"] +
    ['BVH', 'BMI', 'MIG', 'PVI', 'PTI']
)

# =====================================================================
# SÀN NIÊM YẾT (phục vụ luật biên độ HOSE ±7% / HNX ±10% / UPCoM ±15%)
# =====================================================================
# Danh sách mã niêm yết trên HNX (HNX30 và các mã tiêu biểu hàng đầu)
HNX_TICKERS = [
    'BAB', 'BCC', 'BVS', 'CAP', 'CEO', 'C69', 'DTD', 'HHC', 'IDC',
    'IDV', 'L14', 'LAS', 'MBS', 'MST', 'ND2', 'NDN', 'NRC', 'NVB',
    'PVC', 'PVS', 'PVB', 'PVI', 'SCI', 'SHS', 'TAR', 'TNG', 'VC3',
    'VCS', 'VGS'
]

# Danh sách mã giao dịch trên UPCoM (Vốn hóa lớn & thanh khoản hàng đầu)
UPCOM_TICKERS = [
    'AAS', 'ABB', 'ACV', 'BSR', 'BVB', 'C4G', 'CC1', 'DDV', 'DRI',
    'FOX', 'G36', 'GDA', 'GEE', 'HND', 'IDP', 'KLB', 'MCH', 'MML',
    'MSR', 'OIL', 'POS', 'QNS', 'QTP', 'SBS', 'TBD', 'VEA', 'VGI',
    'VBB'
]

EXCHANGE_MAP = {t: "HNX" for t in HNX_TICKERS}
EXCHANGE_MAP.update({t: "UPCOM" for t in UPCOM_TICKERS})


def get_exchange(ticker: str, default: str = None) -> str:
    """Trả về sàn niêm yết của mã. Mặc định HOSE nếu không có trong bản đồ."""
    if default is None:
        from config.settings import DEFAULT_EXCHANGE
        default = DEFAULT_EXCHANGE
    if not ticker:
        return default
    t = ticker.upper().replace("^", "")
    if t in ("VNINDEX", "VN30", "VN30F1M", "HNXINDEX", "UPCOMINDEX"):
        return "INDEX"
    return EXCHANGE_MAP.get(t, default)


# Rổ Tier 1 Core (~150 mã): VN100 + Đại diện 9 ngành ICB + CTCK + 4 Vingroup
_tier1_set = set(VINGROUP_TICKERS)
for sec_list in SECTOR_MAPPING.values():
    _tier1_set.update(sec_list)

# Bổ sung các mã VN100 / thanh khoản lớn phổ biến khác
_extra_tier1 = [
    'BVH', 'BMI', 'MIG', 'GMD', 'HAH', 'VSC', 'PVT',
    'DPM', 'DCM', 'BFC', 'CSV', 'GVR', 'PHR', 'DPR',
    'VGC', 'SZC', 'KBC', 'IDC', 'BCM',
    'VJC', 'HVN', 'SCS', 'ACV',
    'ANV', 'VHC', 'IDI', 'FMC'
]
_tier1_set.update(_extra_tier1)

TIER_1_UNIVERSE = sorted(list(_tier1_set))

# Danh mục phân loại theo Sàn Giao Dịch
HOSE_TICKERS = sorted([t for t in TIER_1_UNIVERSE if get_exchange(t) == "HOSE"])
ALL_EXCHANGES_TICKERS = sorted(list(set(TIER_1_UNIVERSE + HNX_TICKERS + UPCOM_TICKERS)))

EXCHANGE_UNIVERSE_MAP = {
    "TIER_1": TIER_1_UNIVERSE,
    "HOSE": HOSE_TICKERS,
    "HNX": sorted(list(set(HNX_TICKERS))),
    "UPCOM": sorted(list(set(UPCOM_TICKERS))),
    "ALL": ALL_EXCHANGES_TICKERS
}

def get_tickers_by_exchange(exchange: str) -> list:
    """
    Trả về danh sách mã theo sàn hoặc theo nhóm:
    - 'TIER_1': Fast Core (~150 mã liên sàn)
    - 'HOSE' hoặc 'HSX': Sàn HOSE
    - 'HNX': Sàn HNX
    - 'UPCOM': Sàn UPCOM
    - 'ALL': Tất cả 3 sàn (HOSE + HNX + UPCOM)
    """
    key = (exchange or "TIER_1").upper()
    if key in ("HSX", "HOSE"):
        return HOSE_TICKERS
    return EXCHANGE_UNIVERSE_MAP.get(key, TIER_1_UNIVERSE)

# Danh mục tài sản Vĩ mô & Hàng hóa quốc tế
MACRO_COMMODITY_TICKERS = {
    "DX-Y.NYB": "Chỉ số USD (DXY)",
    "VND=X": "Tỷ giá USD/VND",
    "^TNX": "Lợi suất Trái phiếu Mỹ 10 năm (US10Y)",
    "^TYX": "Lợi suất Trái phiếu Mỹ 30 năm (US30Y)",
    "^VIX": "Chỉ số Biến động CBOE (VIX)",
    "GC=F": "Vàng Thế giới (Gold Futures)",
    "BZ=F": "Dầu Brent (Brent Crude)",
    "CL=F": "Dầu WTI (Crude Oil)",
    "HG=F": "Đồng (Copper Futures)",
    "SLX": "Quỹ Thép Thế giới (VanEck Steel ETF)"
}

# Ánh xạ hàng hóa tương ứng với các ngành Việt Nam để tính tương quan Tầng 3
COMMODITY_SECTOR_MAP = {
    "Thép & VLXD": "SLX",
    "Dầu khí & Năng lượng": "BZ=F",
    "Bán lẻ & Tiêu dùng": "GC=F",
    "Công nghệ & Viễn thông": "HG=F"
}
