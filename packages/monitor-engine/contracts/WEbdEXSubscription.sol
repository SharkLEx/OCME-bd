// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title WEbdEXSubscription v1.1.0
 * @author WEbdEX Protocol — https://webdex.io
 * @notice Contrato de assinatura do bdZinho IA no Discord, pago em Token BD (Polygon).
 *
 * @dev Fluxo de assinatura:
 *   1. Usuário aprova BD: `BD.approve(contrato, pricePerMonth * months)`
 *   2. Usuário chama `subscribe(months)` — BD vai direto para a tesouraria.
 *   3. O contrato registra o timestamp de expiração.
 *   4. Bot consulta `isSubscribed(wallet)` para liberar acesso PRO.
 *
 *   IB pode patrocinar usuário via `subscribeFor(wallet, months)`.
 *   Sem custódia — o contrato não retém nenhum token.
 *
 * ── Endereços (Polygon Mainnet) ──────────────────────────────────────────────
 *   Token BD    : 0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d
 *   Deploy/owner: 0xb5Fb0CDaab5784cBE05CcB9D843DaFe4663883C5
 *   Tesouraria  : 0xD6A6d289F65F72b8eAC7364c53506cbde2e2FCD8
 * ─────────────────────────────────────────────────────────────────────────────
 */

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function decimals() external view returns (uint8);
}

contract WEbdEXSubscription {

    // ── Constants ─────────────────────────────────────────────────────────────

    /// @notice Duração de um mês de assinatura (30 dias em segundos).
    uint256 public constant MONTH = 30 days;

    /// @notice Máximo de meses por transação (evita approve excessivo).
    uint256 public constant MAX_MONTHS = 12;

    /// @notice Versão do contrato.
    string  public constant VERSION = "1.1.0";

    // ── State ─────────────────────────────────────────────────────────────────

    /// @notice Endereço do dono/admin do protocolo.
    address public owner;

    /// @notice Tesouraria que recebe os BD das assinaturas.
    address public treasury;

    /// @notice Token BD usado para pagamento.
    IERC20  public immutable bdToken;

    /// @notice Preço de um mês de assinatura em wei (18 decimals).
    uint256 public pricePerMonth;

    /// @notice Se verdadeiro, novas assinaturas estão bloqueadas.
    bool    public paused;

    /// @notice Total de assinaturas realizadas no contrato (histórico acumulado).
    uint256 public totalSubscriptions;

    /// @notice Timestamp de expiração da assinatura por carteira.
    mapping(address => uint256) public subscriptionExpiry;

    // ── Events ────────────────────────────────────────────────────────────────

    /// @notice Emitido quando uma assinatura é criada ou renovada.
    /// @param wallet   Carteira que recebeu o acesso.
    /// @param paidBy   Quem pagou (pode ser IB ou o próprio usuário).
    /// @param months   Quantos meses foram contratados.
    /// @param expiry   Novo timestamp de expiração.
    /// @param paidBD   Total de BD transferido para a tesouraria.
    event Subscribed(
        address indexed wallet,
        address indexed paidBy,
        uint256 months,
        uint256 expiry,
        uint256 paidBD
    );

    event PriceUpdated(uint256 oldPrice, uint256 newPrice);
    event TreasuryUpdated(address oldTreasury, address newTreasury);
    event OwnershipTransferred(address oldOwner, address newOwner);
    event Paused(bool status);

    // ── Modifiers ─────────────────────────────────────────────────────────────

    modifier onlyOwner() {
        require(msg.sender == owner, "WEbdEX: not owner");
        _;
    }

    modifier notPaused() {
        require(!paused, "WEbdEX: contract paused");
        _;
    }

    // ── Constructor ───────────────────────────────────────────────────────────

    constructor() {
        owner    = 0xb5Fb0CDaab5784cBE05CcB9D843DaFe4663883C5;
        treasury = 0xD6A6d289F65F72b8eAC7364c53506cbde2e2FCD8;
        bdToken  = IERC20(0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d);

        // 36.9 BD × 10^18
        pricePerMonth = 36_900_000_000_000_000_000;
    }

    // ── Core ──────────────────────────────────────────────────────────────────

    /**
     * @notice Assina ou renova o acesso ao bdZinho IA por 1 a 12 meses.
     * @dev    Requer aprovação prévia: `BD.approve(contrato, pricePerMonth * months)`.
     *         O BD vai direto para a tesouraria — sem custódia.
     *         Se a assinatura ainda estiver ativa, o período é estendido a partir do expiry atual.
     * @param months Número de meses a contratar (mínimo 1, máximo 12).
     */
    function subscribe(uint256 months) external notPaused {
        require(months >= 1 && months <= MAX_MONTHS, "WEbdEX: invalid months (1-12)");

        uint256 total = pricePerMonth * months;
        require(
            bdToken.transferFrom(msg.sender, treasury, total),
            "WEbdEX: transfer failed - approve BD first"
        );

        _extend(msg.sender, months);
        emit Subscribed(msg.sender, msg.sender, months, subscriptionExpiry[msg.sender], total);
    }

    /**
     * @notice Patrocina a assinatura de outra carteira (uso por IBs ou presentes).
     * @dev    O pagador (msg.sender) aprova e paga; `wallet` recebe o acesso.
     *         Requer: `BD.approve(contrato, pricePerMonth * months)` pelo pagador.
     * @param wallet  Carteira beneficiaria do acesso PRO.
     * @param months  Numero de meses (1-12).
     */
    function subscribeFor(address wallet, uint256 months) external notPaused {
        require(wallet != address(0), "WEbdEX: invalid wallet");
        require(months >= 1 && months <= MAX_MONTHS, "WEbdEX: invalid months (1-12)");

        uint256 total = pricePerMonth * months;
        require(
            bdToken.transferFrom(msg.sender, treasury, total),
            "WEbdEX: transfer failed - approve BD first"
        );

        _extend(wallet, months);
        emit Subscribed(wallet, msg.sender, months, subscriptionExpiry[wallet], total);
    }

    // ── Internal ──────────────────────────────────────────────────────────────

    /// @dev Estende (ou inicia) a assinatura de `wallet` por `months` meses.
    function _extend(address wallet, uint256 months) internal {
        uint256 base = subscriptionExpiry[wallet] > block.timestamp
            ? subscriptionExpiry[wallet]
            : block.timestamp;
        subscriptionExpiry[wallet] = base + (MONTH * months);
        totalSubscriptions += 1;
    }

    // ── Views ─────────────────────────────────────────────────────────────────

    /**
     * @notice Verifica se uma carteira tem acesso PRO ativo.
     * @param wallet Endereço a verificar.
     * @return true se a assinatura não expirou.
     */
    function isSubscribed(address wallet) external view returns (bool) {
        return subscriptionExpiry[wallet] > block.timestamp;
    }

    /**
     * @notice Dias restantes de assinatura.
     * @param wallet Endereço a verificar.
     * @return Dias inteiros restantes (0 se expirado).
     */
    function daysRemaining(address wallet) external view returns (uint256) {
        if (subscriptionExpiry[wallet] <= block.timestamp) return 0;
        return (subscriptionExpiry[wallet] - block.timestamp) / 1 days;
    }

    /**
     * @notice Retorna todas as informações de assinatura em uma única chamada.
     * @param wallet Endereço a consultar.
     * @return active      Se a assinatura está ativa.
     * @return daysLeft    Dias restantes (0 se expirado).
     * @return expiry      Timestamp Unix de expiração.
     * @return priceMonth  Preço atual de um mês em wei.
     */
    function getInfo(address wallet) external view returns (
        bool    active,
        uint256 daysLeft,
        uint256 expiry,
        uint256 priceMonth
    ) {
        expiry     = subscriptionExpiry[wallet];
        active     = expiry > block.timestamp;
        daysLeft   = active ? (expiry - block.timestamp) / 1 days : 0;
        priceMonth = pricePerMonth;
    }

    /**
     * @notice Custo total para assinar N meses.
     * @param months Número de meses.
     * @return Total em wei de BD necessário.
     */
    function quoteSubscription(uint256 months) external view returns (uint256) {
        require(months >= 1 && months <= MAX_MONTHS, "WEbdEX: meses invalidos (1-12)");
        return pricePerMonth * months;
    }

    // ── Admin ─────────────────────────────────────────────────────────────────

    /**
     * @notice Atualiza o preço mensal da assinatura.
     * @param newPrice Novo preço em wei (ex: 36.9 BD = 36900000000000000000).
     */
    function setPrice(uint256 newPrice) external onlyOwner {
        require(newPrice > 0, "WEbdEX: preco invalido");
        emit PriceUpdated(pricePerMonth, newPrice);
        pricePerMonth = newPrice;
    }

    /**
     * @notice Atualiza o endereço da tesouraria.
     * @param newTreasury Novo endereço que receberá os BD.
     */
    function setTreasury(address newTreasury) external onlyOwner {
        require(newTreasury != address(0), "WEbdEX: zero address");
        emit TreasuryUpdated(treasury, newTreasury);
        treasury = newTreasury;
    }

    /**
     * @notice Pausa ou despausa novas assinaturas.
     * @param status true para pausar, false para reativar.
     */
    function setPaused(bool status) external onlyOwner {
        paused = status;
        emit Paused(status);
    }

    /**
     * @notice Transfere a propriedade do contrato para outro endereço.
     * @param newOwner Novo owner/admin.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "WEbdEX: zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /**
     * @notice Admin pode conceder acesso PRO manualmente (onboarding, suporte).
     * @param wallet Carteira beneficiária.
     * @param months Meses a conceder.
     */
    function grantAccess(address wallet, uint256 months) external onlyOwner {
        require(wallet != address(0), "WEbdEX: zero address");
        require(months >= 1 && months <= MAX_MONTHS, "WEbdEX: meses invalidos (1-12)");
        _extend(wallet, months);
        emit Subscribed(wallet, owner, months, subscriptionExpiry[wallet], 0);
    }
}
