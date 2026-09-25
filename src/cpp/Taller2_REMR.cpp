// PEA-i UPC: consola y backend JSON para Tkinter en C++17.
// Fuente unica para la entrega; los CSV compartidos se documentan en docs/esquema_datos.md.
#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <unordered_map>
#include <utility>
#include <vector>
#include <ctime>
#ifdef _WIN32
#include <windows.h>
#endif

namespace pea {
namespace fs = std::filesystem;
using Row = std::map<std::string, std::string>;
using Rows = std::vector<Row>;

struct DataError : std::runtime_error {
    using std::runtime_error::runtime_error;
};

const std::array<std::string, 4> ENTITY_KINDS = {
    "grupos", "investigadores", "productos", "planes"
};
const std::array<std::string, 3> RELATION_KINDS = {
    "membresias", "autorias", "grupos_productos"
};
const std::array<std::string, 7> ALL_KINDS = {
    "grupos", "investigadores", "productos", "planes",
    "membresias", "autorias", "grupos_productos"
};
constexpr std::size_t MAX_FIELD_LENGTH = 100000;
constexpr std::size_t MAX_CSV_ROWS = 500000;
const std::map<std::string, std::vector<std::string>> FIELDS = {
    {"grupos", {"id", "nombre", "codigo_gruplac", "fecha_creacion", "unidad", "responsable",
                "categoria", "descripcion", "objetivos", "mision", "vision", "lineas", "url", "fuente", "activo"}},
    {"investigadores", {"id", "nombre", "codigo_cvlac", "afiliacion", "categoria", "contacto", "url", "fuente", "activo"}},
    {"productos", {"id", "titulo", "anio", "fecha", "familia", "tipologia", "categoria",
                   "validacion", "observacion", "doi", "url", "fuente", "activo"}},
    {"planes", {"id", "grupo_id", "nombre", "inicio", "fin", "objetivo", "indicador", "meta", "actividad", "activo"}},
    {"membresias", {"grupo_id", "investigador_id", "rol", "inicio", "fin", "activo"}},
    {"autorias", {"producto_id", "investigador_id", "orden", "rol", "activo"}},
    {"grupos_productos", {"grupo_id", "producto_id", "origen", "activo"}}
};
const std::map<std::string, std::array<std::string, 4>> RELATION_ENDS = {
    {"membresias", {"grupo_id", "investigador_id", "grupos", "investigadores"}},
    {"autorias", {"producto_id", "investigador_id", "productos", "investigadores"}},
    {"grupos_productos", {"grupo_id", "producto_id", "grupos", "productos"}}
};
const std::map<std::string, std::vector<std::string>> REQUIRED = {
    {"grupos", {"id", "nombre"}}, {"investigadores", {"id", "nombre"}},
    {"productos", {"id", "titulo"}}, {"planes", {"id", "grupo_id", "nombre"}}
};
const std::map<std::string, std::string> LABELS = {
    {"id", "ID"}, {"nombre", "Nombre"},
    {"codigo_gruplac", "Codigo GrupLAC"}, {"fecha_creacion", "Fecha creacion"},
    {"unidad", "Unidad academica"}, {"responsable", "Responsable"},
    {"categoria", "Categoria"}, {"descripcion", "Descripcion"}, {"objetivos", "Objetivos"},
    {"mision", "Mision"}, {"vision", "Vision"}, {"lineas", "Lineas"}, {"url", "URL"},
    {"fuente", "Fuente"}, {"activo", "Activo"}, {"codigo_cvlac", "Codigo CvLAC"},
    {"afiliacion", "Afiliacion"}, {"contacto", "Contacto publico"}, {"titulo", "Titulo"},
    {"anio", "Anio"}, {"fecha", "Fecha"}, {"familia", "Familia"}, {"tipologia", "Tipologia"},
    {"validacion", "Validacion"}, {"observacion", "Observacion"}, {"doi", "DOI"},
    {"grupo_id", "Grupo ID"}, {"investigador_id", "Investigador ID"},
    {"producto_id", "Producto ID"}, {"inicio", "Inicio"}, {"fin", "Fin"},
    {"objetivo", "Objetivo"}, {"indicador", "Indicador"}, {"meta", "Meta"},
    {"actividad", "Actividad"}, {"rol", "Rol"}, {"orden", "Orden"}, {"origen", "Origen"}
};

const std::string& field(const Row& row, const std::string& key) {
    static const std::string empty;
    auto found = row.find(key);
    return found == row.end() ? empty : found->second;
}
std::string label(const std::string& key) {
    auto found = LABELS.find(key);
    return found == LABELS.end() ? key : found->second;
}
std::string trim(std::string text) {
    auto nonspace = [](unsigned char ch) { return !std::isspace(ch); };
    text.erase(text.begin(), std::find_if(text.begin(), text.end(), nonspace));
    text.erase(std::find_if(text.rbegin(), text.rend(), nonspace).base(), text.end());
    return text;
}
std::string lowercase(std::string text) {
    std::transform(text.begin(), text.end(), text.begin(),
                   [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return text;
}
bool startsWith(const std::string& value, const std::string& prefix) {
    return value.size() >= prefix.size() && value.compare(0, prefix.size(), prefix) == 0;
}
bool digits(const std::string& text) {
    return !text.empty() && std::all_of(text.begin(), text.end(),
        [](unsigned char ch) { return std::isdigit(ch) != 0; });
}
bool validUtf8(const std::string& value) {
    for (std::size_t i = 0; i < value.size();) {
        const auto first = static_cast<unsigned char>(value[i]);
        if (first < 0x80) { ++i; continue; }
        int extra = 0;
        if (first >= 0xc2 && first <= 0xdf) extra = 1;
        else if (first >= 0xe0 && first <= 0xef) extra = 2;
        else if (first >= 0xf0 && first <= 0xf4) extra = 3;
        else return false;
        if (i + static_cast<std::size_t>(extra) >= value.size()) return false;
        const auto second = static_cast<unsigned char>(value[i + 1]);
        if (second < 0x80 || second > 0xbf ||
            (first == 0xe0 && second < 0xa0) ||
            (first == 0xed && second > 0x9f) ||
            (first == 0xf0 && second < 0x90) ||
            (first == 0xf4 && second > 0x8f)) return false;
        for (int step = 2; step <= extra; ++step) {
            const auto part = static_cast<unsigned char>(value[i + static_cast<std::size_t>(step)]);
            if (part < 0x80 || part > 0xbf) return false;
        }
        i += static_cast<std::size_t>(extra + 1);
    }
    return true;
}
int currentYear() {
    std::time_t now = std::time(nullptr);
    std::tm local{};
#ifdef _WIN32
    localtime_s(&local, &now);
#else
    localtime_r(&now, &local);
#endif
    return local.tm_year + 1900;
}
std::string nowIso() {
    std::time_t now = std::time(nullptr);
    std::tm local{};
#ifdef _WIN32
    localtime_s(&local, &now);
#else
    localtime_r(&now, &local);
#endif
    std::ostringstream out;
    out << std::put_time(&local, "%Y-%m-%dT%H:%M:%S");
    return out.str();
}
fs::path pathFromUtf8(const std::string& value) {
#ifdef _WIN32
    if (value.empty()) return {};
    const int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                                        static_cast<int>(value.size()), nullptr, 0);
    if (size <= 0) throw DataError("Ruta UTF-8 invalida");
    std::wstring wide(static_cast<std::size_t>(size), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                           static_cast<int>(value.size()), wide.data(), size) <= 0)
        throw DataError("Ruta UTF-8 invalida");
    return fs::path(wide);
#else
    return fs::path(value);
#endif
}
bool validDate(const std::string& text) {
    if (text.size() != 10 || text[4] != '-' || text[7] != '-') return false;
    const auto numeric = text.substr(0, 4) + text.substr(5, 2) + text.substr(8, 2);
    if (!digits(numeric)) return false;
    int year = std::stoi(text.substr(0, 4));
    int month = std::stoi(text.substr(5, 2));
    int day = std::stoi(text.substr(8, 2));
    if (year < 1 || month < 1 || month > 12) return false;
    const bool leap = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    const std::array<int, 12> days = {31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    return day >= 1 && day <= days[static_cast<std::size_t>(month - 1)];
}
std::string normalizedExternal(const std::string& kind, std::string text) {
    text = lowercase(trim(text));
    if (kind == "productos" && startsWith(text, "https://doi.org/")) text.erase(0, 16);
    return text;
}
std::string externalField(const std::string& kind) {
    if (kind == "grupos") return "codigo_gruplac";
    if (kind == "investigadores") return "codigo_cvlac";
    if (kind == "productos") return "doi";
    return "";
}
bool rowMatches(const Row& row, const std::string& query) {
    if (query.empty()) return true;
    for (const auto& item : row)
        if (lowercase(item.second).find(query) != std::string::npos) return true;
    return false;
}
struct Page {
    Rows rows;
    std::size_t total = 0;
};
Row cleanRow(const std::string& kind, const Row& input) {
    auto spec = FIELDS.find(kind);
    if (spec == FIELDS.end()) throw DataError("Tipo desconocido: " + kind);
    for (const auto& item : input) {
        if (std::find(spec->second.begin(), spec->second.end(), item.first) == spec->second.end())
            throw DataError("Columna desconocida: " + item.first);
    }
    Row row;
    for (const auto& name : spec->second) row[name] = trim(field(input, name));
    if (row["activo"].empty()) row["activo"] = "1";
    if (row["activo"] != "0" && row["activo"] != "1") throw DataError("Activo debe ser 0 o 1");
    auto required = REQUIRED.find(kind);
    if (required != REQUIRED.end()) {
        for (const auto& name : required->second)
            if (row[name].empty()) throw DataError("Falta " + label(name));
    }
    for (const auto& name : spec->second) {
        if (name.size() >= 3 && name.substr(name.size() - 3) == "_id" && row[name].empty())
            throw DataError("Falta " + label(name));
    }
    if (kind == "productos") {
        if (!row["fecha"].empty() && row["anio"].empty()) row["anio"] = row["fecha"].substr(0, 4);
        if (!row["anio"].empty()) {
            if (!digits(row["anio"])) throw DataError("Anio invalido");
            int year;
            try { year = std::stoi(row["anio"]); }
            catch (const std::exception&) { throw DataError("Anio invalido"); }
            if (year < 1900 || year > currentYear() + 1) throw DataError("Anio fuera de rango");
        }
        if (row["validacion"].empty()) row["validacion"] = "pendiente";
        if (row["validacion"] != "pendiente" && row["validacion"] != "validado" && row["validacion"] != "rechazado")
            throw DataError("Validacion: pendiente, validado o rechazado");
    }
    if (kind == "autorias" && !row["orden"].empty()) {
        if (!digits(row["orden"])) throw DataError("Orden de autor debe ser positivo");
        try {
            if (std::stoll(row["orden"]) < 1) throw DataError("Orden de autor debe ser positivo");
        } catch (const std::out_of_range&) {
            throw DataError("Orden de autor fuera de rango");
        }
    }
    for (const auto& name : {"fecha", "fecha_creacion", "inicio", "fin"}) {
        if (row.count(name) && !row[name].empty() && !validDate(row[name]))
            throw DataError(label(name) + " debe ser AAAA-MM-DD");
    }
    if (kind == "productos" && !row["fecha"].empty() && !row["anio"].empty() &&
        row["fecha"].substr(0, 4) != row["anio"])
        throw DataError("El anio y la fecha del producto no coinciden");
    if ((kind == "planes" || kind == "membresias") && !row["inicio"].empty() &&
        !row["fin"].empty() && row["inicio"] > row["fin"])
        throw DataError("La fecha final precede la inicial");
    for (const auto& [name, value] : row)
        if (value.size() > MAX_FIELD_LENGTH)
            throw DataError(label(name) + " supera el tamano permitido");
    return row;
}

// Nodos doblemente enlazados: la lista es la fuente de verdad; el mapa solo ubica un nodo.
class DoublyList {
    struct Node {
        Row row;
        Node* prev = nullptr;
        Node* next = nullptr;
        explicit Node(Row value) : row(std::move(value)) {}
    };
    Node* head_ = nullptr;
    Node* tail_ = nullptr;
    std::unordered_map<std::string, Node*> index_;
public:
    DoublyList() = default;
    DoublyList(const DoublyList&) = delete;
    DoublyList& operator=(const DoublyList&) = delete;
    DoublyList(DoublyList&& other) noexcept { swap(other); }
    DoublyList& operator=(DoublyList&& other) noexcept {
        if (this != &other) { clear(); swap(other); }
        return *this;
    }
    ~DoublyList() { clear(); }
    void swap(DoublyList& other) noexcept {
        std::swap(head_, other.head_);
        std::swap(tail_, other.tail_);
        index_.swap(other.index_);
    }
    void clear() noexcept {
        while (head_) {
            Node* next = head_->next;
            delete head_;
            head_ = next;
        }
        tail_ = nullptr;
        index_.clear();
    }
    std::size_t size() const { return index_.size(); }
    Row* get(const std::string& id) const {
        auto found = index_.find(id);
        return found == index_.end() ? nullptr : &found->second->row;
    }
    void append(Row row) {
        const auto id = field(row, "id");
        if (index_.count(id)) throw DataError("ID duplicado: " + id);
        auto node = std::make_unique<Node>(std::move(row));
        index_.emplace(id, node.get());
        node->prev = tail_;
        if (tail_) tail_->next = node.get();
        else head_ = node.get();
        tail_ = node.release();
    }
    void erase(const std::string& id) {
        auto found = index_.find(id);
        if (found == index_.end()) throw DataError("No existe ID " + id);
        Node* node = found->second;
        if (node->prev) node->prev->next = node->next;
        else head_ = node->next;
        if (node->next) node->next->prev = node->prev;
        else tail_ = node->prev;
        index_.erase(found);
        delete node;
    }
    Rows rows() const {
        Rows result;
        result.reserve(index_.size());
        for (Node* node = head_; node; node = node->next) result.push_back(node->row);
        return result;
    }
    Page page(std::size_t offset, std::size_t limit, const std::string& query) const {
        Page result;
        if (query.empty()) {
            result.total = index_.size();
            std::size_t index = 0;
            for (Node* node = head_; node && result.rows.size() < limit; node = node->next, ++index)
                if (index >= offset) result.rows.push_back(node->row);
            return result;
        }
        for (Node* node = head_; node; node = node->next) {
            if (!rowMatches(node->row, query)) continue;
            if (result.total >= offset && result.rows.size() < limit)
                result.rows.push_back(node->row);
            ++result.total;
        }
        return result;
    }
    std::size_t activeCount() const {
        std::size_t count = 0;
        for (Node* node = head_; node; node = node->next)
            if (field(node->row, "activo") == "1") ++count;
        return count;
    }
    void forEach(const std::function<void(const Row&)>& visit) const {
        for (Node* node = head_; node; node = node->next) visit(node->row);
    }
    Rows backwards() const {
        Rows result;
        for (Node* node = tail_; node; node = node->prev) result.push_back(node->row);
        return result;
    }
};

// Un nodo de relacion aparece en una cadena por cada extremo (multilista).
class MultiList {
    struct Node {
        Row row;
        std::string left;
        std::string right;
        Node* nextLeft = nullptr;
        Node* nextRight = nullptr;
        Node(Row value, std::string lhs, std::string rhs)
            : row(std::move(value)), left(std::move(lhs)), right(std::move(rhs)) {}
    };
    std::string leftField_;
    std::string rightField_;
    std::map<std::string, Node*> leftHeads_;
    std::map<std::string, Node*> rightHeads_;
    std::map<std::pair<std::string, std::string>, Node*> pairs_;
public:
    MultiList() = default;
    MultiList(std::string left, std::string right)
        : leftField_(std::move(left)), rightField_(std::move(right)) {}
    MultiList(const MultiList&) = delete;
    MultiList& operator=(const MultiList&) = delete;
    MultiList(MultiList&& other) noexcept { swap(other); }
    MultiList& operator=(MultiList&& other) noexcept {
        if (this != &other) { clear(); swap(other); }
        return *this;
    }
    ~MultiList() { clear(); }
    void swap(MultiList& other) noexcept {
        leftField_.swap(other.leftField_);
        rightField_.swap(other.rightField_);
        leftHeads_.swap(other.leftHeads_);
        rightHeads_.swap(other.rightHeads_);
        pairs_.swap(other.pairs_);
    }
    void clear() noexcept {
        for (const auto& item : pairs_) delete item.second;
        pairs_.clear();
        leftHeads_.clear();
        rightHeads_.clear();
    }
    std::size_t size() const { return pairs_.size(); }
    Row* get(const std::string& left, const std::string& right) const {
        auto found = pairs_.find({left, right});
        return found == pairs_.end() ? nullptr : &found->second->row;
    }
    void add(Row row) {
        const std::string left = field(row, leftField_);
        const std::string right = field(row, rightField_);
        if (pairs_.count({left, right})) throw DataError("Relacion duplicada: " + left + " / " + right);
        auto node = std::make_unique<Node>(std::move(row), left, right);
        auto leftHead = leftHeads_.find(left);
        auto rightHead = rightHeads_.find(right);
        bool insertedLeft = false, insertedRight = false;
        try {
            if (leftHead == leftHeads_.end()) {
                leftHead = leftHeads_.emplace(left, nullptr).first;
                insertedLeft = true;
            }
            if (rightHead == rightHeads_.end()) {
                rightHead = rightHeads_.emplace(right, nullptr).first;
                insertedRight = true;
            }
            pairs_.emplace(std::make_pair(left, right), node.get());
        } catch (...) {
            if (insertedLeft) leftHeads_.erase(left);
            if (insertedRight) rightHeads_.erase(right);
            throw;
        }
        node->nextLeft = leftHead->second;
        node->nextRight = rightHead->second;
        leftHead->second = node.get();
        rightHead->second = node.release();
    }
    void erase(const std::string& left, const std::string& right) {
        auto found = pairs_.find({left, right});
        if (found == pairs_.end()) throw DataError("No existe esa relacion");
        Node* node = found->second;
        Node** cursor = &leftHeads_.at(left);
        while (*cursor != node) cursor = &(*cursor)->nextLeft;
        *cursor = node->nextLeft;
        if (!leftHeads_[left]) leftHeads_.erase(left);
        cursor = &rightHeads_.at(right);
        while (*cursor != node) cursor = &(*cursor)->nextRight;
        *cursor = node->nextRight;
        if (!rightHeads_[right]) rightHeads_.erase(right);
        pairs_.erase(found);
        delete node;
    }
    Rows byLeft(const std::string& key) const {
        Rows result;
        auto found = leftHeads_.find(key);
        for (Node* node = found == leftHeads_.end() ? nullptr : found->second;
             node; node = node->nextLeft) result.push_back(node->row);
        return result;
    }
    Rows byRight(const std::string& key) const {
        Rows result;
        auto found = rightHeads_.find(key);
        for (Node* node = found == rightHeads_.end() ? nullptr : found->second;
             node; node = node->nextRight) result.push_back(node->row);
        return result;
    }
    Page relatedPage(const std::string& key, bool fromLeft, std::size_t offset,
                     std::size_t limit, bool activeOnly = false) const {
        Page result;
        Node* node = nullptr;
        if (fromLeft) {
            auto found = leftHeads_.find(key);
            if (found != leftHeads_.end()) node = found->second;
        } else {
            auto found = rightHeads_.find(key);
            if (found != rightHeads_.end()) node = found->second;
        }
        for (; node; node = fromLeft ? node->nextLeft : node->nextRight) {
            if (activeOnly && field(node->row, "activo") != "1") continue;
            if (result.total >= offset && result.rows.size() < limit)
                result.rows.push_back(node->row);
            ++result.total;
        }
        return result;
    }
    void forEachRelated(const std::string& key, bool fromLeft,
                        const std::function<void(const Row&)>& visit) const {
        Node* node = nullptr;
        if (fromLeft) {
            auto found = leftHeads_.find(key);
            if (found != leftHeads_.end()) node = found->second;
        } else {
            auto found = rightHeads_.find(key);
            if (found != rightHeads_.end()) node = found->second;
        }
        for (; node; node = fromLeft ? node->nextLeft : node->nextRight) visit(node->row);
    }
    Rows rows() const {
        Rows result;
        result.reserve(pairs_.size());
        for (const auto& entry : leftHeads_)
            for (Node* node = entry.second; node; node = node->nextLeft) result.push_back(node->row);
        std::sort(result.begin(), result.end(), [&](const Row& a, const Row& b) {
            return std::pair{field(a, leftField_), field(a, rightField_)} <
                   std::pair{field(b, leftField_), field(b, rightField_)};
        });
        return result;
    }
    Page page(std::size_t offset, std::size_t limit, const std::string& query) const {
        Page result;
        if (query.empty()) {
            result.total = pairs_.size();
            std::size_t index = 0;
            for (auto it = pairs_.begin(); it != pairs_.end() && result.rows.size() < limit; ++it, ++index)
                if (index >= offset) result.rows.push_back(it->second->row);
            return result;
        }
        for (const auto& entry : pairs_) {
            const Row& row = entry.second->row;
            if (!rowMatches(row, query)) continue;
            if (result.total >= offset && result.rows.size() < limit) result.rows.push_back(row);
            ++result.total;
        }
        return result;
    }
    void forEach(const std::function<void(const Row&)>& visit) const {
        for (const auto& entry : pairs_) visit(entry.second->row);
    }
};

class LinkedStack {
    struct Node {
        std::string value;
        Node* next = nullptr;
        Node(std::string text, Node* following) : value(std::move(text)), next(following) {}
    };
    Node* top_ = nullptr;
    std::size_t length_ = 0;
    static constexpr std::size_t LIMIT = 30;
public:
    LinkedStack() = default;
    LinkedStack(const LinkedStack&) = delete;
    LinkedStack& operator=(const LinkedStack&) = delete;
    LinkedStack(LinkedStack&& other) noexcept { swap(other); }
    LinkedStack& operator=(LinkedStack&& other) noexcept {
        if (this != &other) { clear(); swap(other); }
        return *this;
    }
    ~LinkedStack() { clear(); }
    void swap(LinkedStack& other) noexcept {
        std::swap(top_, other.top_);
        std::swap(length_, other.length_);
    }
    std::size_t size() const { return length_; }
    void push(std::string value) {
        top_ = new Node(std::move(value), top_);
        ++length_;
        if (length_ > LIMIT) {
            Node* node = top_;
            for (std::size_t i = 1; i < LIMIT; ++i) node = node->next;
            delete node->next;
            node->next = nullptr;
            length_ = LIMIT;
        }
    }
    std::optional<std::string> peek() const {
        if (!top_) return std::nullopt;
        return top_->value;
    }
    std::optional<std::string> pop() {
        if (!top_) return std::nullopt;
        Node* node = top_;
        std::string value = std::move(node->value);
        top_ = node->next;
        delete node;
        --length_;
        return value;
    }
    void clear() noexcept {
        while (top_) {
            Node* next = top_->next;
            delete top_;
            top_ = next;
        }
        length_ = 0;
    }
    std::vector<std::string> values() const {
        std::vector<std::string> result;
        for (Node* node = top_; node; node = node->next) result.push_back(node->value);
        return result;
    }
    void forEach(const std::function<void(const std::string&)>& visit) const {
        for (Node* node = top_; node; node = node->next) visit(node->value);
    }
};

class LinkedQueue {
    struct Node {
        Row value;
        Node* next = nullptr;
        explicit Node(Row row) : value(std::move(row)) {}
    };
    Node* front_ = nullptr;
    Node* rear_ = nullptr;
    std::size_t length_ = 0;
public:
    LinkedQueue() = default;
    LinkedQueue(const LinkedQueue&) = delete;
    LinkedQueue& operator=(const LinkedQueue&) = delete;
    LinkedQueue(LinkedQueue&& other) noexcept { swap(other); }
    LinkedQueue& operator=(LinkedQueue&& other) noexcept {
        if (this != &other) { clear(); swap(other); }
        return *this;
    }
    ~LinkedQueue() { clear(); }
    void swap(LinkedQueue& other) noexcept {
        std::swap(front_, other.front_);
        std::swap(rear_, other.rear_);
        std::swap(length_, other.length_);
    }
    void clear() noexcept {
        while (front_) {
            Node* next = front_->next;
            delete front_;
            front_ = next;
        }
        rear_ = nullptr;
        length_ = 0;
    }
    std::size_t size() const { return length_; }
    const Row* peek() const { return front_ ? &front_->value : nullptr; }
    const Row* back() const { return rear_ ? &rear_->value : nullptr; }
    void enqueue(Row row) {
        Node* node = new Node(std::move(row));
        if (rear_) rear_->next = node;
        else front_ = node;
        rear_ = node;
        ++length_;
    }
    void prepend(Row row) {
        Node* node = new Node(std::move(row));
        node->next = front_;
        front_ = node;
        if (!rear_) rear_ = node;
        ++length_;
    }
    Row remove(const std::string& id) {
        Node* previous = nullptr;
        Node* node = front_;
        while (node && field(node->value, "id") != id) {
            previous = node;
            node = node->next;
        }
        if (!node) throw DataError("Trabajo de cola no encontrado");
        if (previous) previous->next = node->next;
        else front_ = node->next;
        if (rear_ == node) rear_ = previous;
        Row value = std::move(node->value);
        delete node;
        --length_;
        return value;
    }
    std::optional<Row> dequeue() {
        if (!front_) return std::nullopt;
        Node* node = front_;
        Row value = std::move(node->value);
        front_ = node->next;
        if (!front_) rear_ = nullptr;
        delete node;
        --length_;
        return value;
    }
    Rows rows() const {
        Rows result;
        for (Node* node = front_; node; node = node->next) result.push_back(node->value);
        return result;
    }
    Page page(std::size_t offset, std::size_t limit) const {
        Page result;
        result.total = length_;
        std::size_t index = 0;
        for (Node* node = front_; node && result.rows.size() < limit; node = node->next, ++index)
            if (index >= offset) result.rows.push_back(node->value);
        return result;
    }
    void forEach(const std::function<void(const Row&)>& visit) const {
        for (Node* node = front_; node; node = node->next) visit(node->value);
    }
};

std::string storageCell(const std::string& value) {
    if (!value.empty() && std::string("=+-@\t\r'").find(value.front()) != std::string::npos)
        return "'" + value;
    return value;
}

// Lee registros uno a uno; admite BOM, comillas, CRLF y saltos de linea dentro de celdas.
std::size_t readCsvEach(const fs::path& path, const std::vector<std::string>& requiredFields,
                        const std::function<void(Row, std::size_t)>& visit,
                        bool encoded = false) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw DataError("No se pudo abrir " + path.string());
    char bom[3]{};
    input.read(bom, 3);
    if (input.gcount() != 3 || std::string(bom, 3) != "\xEF\xBB\xBF") {
        input.clear();
        input.seekg(0);
    }
    std::vector<std::string> header;
    std::vector<std::string> record;
    std::string cell;
    bool quoted = false, closedQuote = false, touched = false, hasHeader = false;
    std::size_t number = 0;
    auto finish = [&] {
        record.push_back(std::move(cell));
        cell.clear();
        ++number;
        for (const auto& value : record)
            if (!validUtf8(value))
                throw DataError(path.filename().string() + ", fila " + std::to_string(number) +
                                ": texto no es UTF-8 valido");
        if (!hasHeader) {
            header = std::move(record);
            const std::set<std::string> expected(requiredFields.begin(), requiredFields.end());
            const std::set<std::string> actual(header.begin(), header.end());
            if (header.size() != requiredFields.size() || actual != expected)
                throw DataError("Encabezados incorrectos en " + path.filename().string());
            hasHeader = true;
        } else {
            if (number - 1 > MAX_CSV_ROWS)
                throw DataError(path.filename().string() + ": demasiadas filas");
            if (record.size() != header.size())
                throw DataError(path.filename().string() + ", fila " + std::to_string(number) + " malformada");
            Row row;
            for (std::size_t i = 0; i < header.size(); ++i) {
                std::string value = std::move(record[i]);
                if (encoded && !value.empty() && value.front() == '\'') value.erase(0, 1);
                row[header[i]] = std::move(value);
            }
            visit(std::move(row), number);
        }
        record.clear();
        touched = false;
        closedQuote = false;
    };
    char ch;
    while (input.get(ch)) {
        if (quoted) {
            if (ch == '"') {
                if (input.peek() == '"') { cell.push_back('"'); input.get(); }
                else { quoted = false; closedQuote = true; }
            } else cell.push_back(ch);
            touched = true;
        } else if (ch == '"') {
            if (!cell.empty() || closedQuote) throw DataError("Comilla CSV mal ubicada");
            quoted = true;
            touched = true;
        } else if (ch == ',') {
            record.push_back(std::move(cell));
            cell.clear();
            closedQuote = false;
            touched = true;
        } else if (ch == '\r' || ch == '\n') {
            finish();
            if (ch == '\r' && input.peek() == '\n') input.get();
        } else {
            if (closedQuote) throw DataError("Texto despues de una comilla CSV de cierre");
            cell.push_back(ch);
            touched = true;
        }
    }
    if (!input.eof()) throw DataError("Error al leer " + path.string());
    if (quoted) throw DataError("Comillas CSV sin cerrar");
    if (touched || !record.empty() || !cell.empty()) finish();
    if (!hasHeader) throw DataError("CSV sin encabezados: " + path.string());
    return number - 1;
}
std::string csvCell(const std::string& value) {
    if (value.find_first_of(",\"\n\r") == std::string::npos) return value;
    std::string result = "\"";
    for (char ch : value) {
        if (ch == '"') result += "\"\"";
        else result.push_back(ch);
    }
    return result + "\"";
}
void writeCsv(const fs::path& path, const std::vector<std::string>& header, const Rows& rows) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) throw DataError("No se pudo escribir " + path.string());
    for (std::size_t i = 0; i < header.size(); ++i)
        output << (i ? "," : "") << csvCell(header[i]);
    output << '\n';
    for (const Row& row : rows) {
        for (std::size_t i = 0; i < header.size(); ++i)
            output << (i ? "," : "") << csvCell(field(row, header[i]));
        output << '\n';
    }
    output.flush();
    if (!output) throw DataError("No se pudo completar " + path.string());
}
void writeCsvEach(const fs::path& path, const std::vector<std::string>& header,
                  const std::function<void(const std::function<void(const Row&)>&)>& produce,
                  bool encoded = false) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) throw DataError("No se pudo escribir " + path.string());
    for (std::size_t i = 0; i < header.size(); ++i)
        output << (i ? "," : "") << csvCell(header[i]);
    output << '\n';
    produce([&](const Row& row) {
        for (std::size_t i = 0; i < header.size(); ++i)
            output << (i ? "," : "") << csvCell(encoded ? storageCell(field(row, header[i])) : field(row, header[i]));
        output << '\n';
    });
    output.flush();
    if (!output) throw DataError("No se pudo completar " + path.string());
}

std::string jsonString(const std::string& value) {
    const char* hex = "0123456789abcdef";
    std::string result = "\"";
    for (unsigned char ch : value) {
        switch (ch) {
            case '"': result += "\\\""; break;
            case '\\': result += "\\\\"; break;
            case '\n': result += "\\n"; break;
            case '\r': result += "\\r"; break;
            case '\t': result += "\\t"; break;
            case '\b': result += "\\b"; break;
            case '\f': result += "\\f"; break;
            default:
                if (ch < 0x20) {
                    result += "\\u00";
                    result.push_back(hex[ch >> 4]);
                    result.push_back(hex[ch & 15]);
                } else {
                    result.push_back(static_cast<char>(ch));
                }
        }
    }
    return result + "\"";
}
void appendUtf8(std::string& output, std::uint32_t codepoint) {
    if (codepoint <= 0x7f) output.push_back(static_cast<char>(codepoint));
    else if (codepoint <= 0x7ff) {
        output.push_back(static_cast<char>(0xc0 | (codepoint >> 6)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
    } else if (codepoint <= 0xffff) {
        output.push_back(static_cast<char>(0xe0 | (codepoint >> 12)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
    } else {
        output.push_back(static_cast<char>(0xf0 | (codepoint >> 18)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 12) & 0x3f)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
    }
}
class SnapshotParser {
    const std::string& text_;
    std::size_t pos_ = 0;
    void whitespace() {
        while (pos_ < text_.size() && std::isspace(static_cast<unsigned char>(text_[pos_]))) ++pos_;
    }
    bool consume(char expected) {
        whitespace();
        if (pos_ < text_.size() && text_[pos_] == expected) { ++pos_; return true; }
        return false;
    }
    void expect(char expected) {
        if (!consume(expected)) throw DataError("JSON malformado");
    }
    std::uint32_t hex4() {
        if (pos_ + 4 > text_.size()) throw DataError("Escape Unicode incompleto");
        std::uint32_t value = 0;
        for (int i = 0; i < 4; ++i) {
            char ch = text_[pos_++];
            value <<= 4;
            if (ch >= '0' && ch <= '9') value += static_cast<unsigned>(ch - '0');
            else if (ch >= 'a' && ch <= 'f') value += static_cast<unsigned>(ch - 'a' + 10);
            else if (ch >= 'A' && ch <= 'F') value += static_cast<unsigned>(ch - 'A' + 10);
            else throw DataError("Escape Unicode invalido");
        }
        return value;
    }
    std::string string() {
        expect('"');
        std::string result;
        while (pos_ < text_.size()) {
            char ch = text_[pos_++];
            if (ch == '"') return result;
            if (static_cast<unsigned char>(ch) < 0x20) throw DataError("Control JSON invalido");
            if (ch != '\\') { result.push_back(ch); continue; }
            if (pos_ == text_.size()) throw DataError("Escape JSON incompleto");
            switch (text_[pos_++]) {
                case '"': result.push_back('"'); break;
                case '\\': result.push_back('\\'); break;
                case '/': result.push_back('/'); break;
                case 'n': result.push_back('\n'); break;
                case 'r': result.push_back('\r'); break;
                case 't': result.push_back('\t'); break;
                case 'b': result.push_back('\b'); break;
                case 'f': result.push_back('\f'); break;
                case 'u': {
                    auto codepoint = hex4();
                    if (codepoint >= 0xd800 && codepoint <= 0xdbff) {
                        if (pos_ + 2 > text_.size() || text_[pos_++] != '\\' || text_[pos_++] != 'u')
                            throw DataError("Par sustituto Unicode incompleto");
                        auto low = hex4();
                        if (low < 0xdc00 || low > 0xdfff) throw DataError("Par sustituto Unicode invalido");
                        codepoint = 0x10000 + ((codepoint - 0xd800) << 10) + low - 0xdc00;
                    } else if (codepoint >= 0xdc00 && codepoint <= 0xdfff) {
                        throw DataError("Par sustituto Unicode invalido");
                    }
                    appendUtf8(result, codepoint);
                    break;
                }
                default: throw DataError("Escape JSON desconocido");
            }
        }
        throw DataError("Cadena JSON sin cerrar");
    }
    Row row() {
        Row result;
        expect('{');
        if (consume('}')) return result;
        do {
            std::string key = string();
            expect(':');
            if (!result.emplace(key, string()).second) throw DataError("Clave JSON duplicada");
        } while (consume(','));
        expect('}');
        return result;
    }
    Rows rows() {
        Rows result;
        expect('[');
        if (consume(']')) return result;
        do { result.push_back(row()); } while (consume(','));
        expect(']');
        return result;
    }
public:
    explicit SnapshotParser(const std::string& text) : text_(text) {}
    Row parseRow() {
        Row result = row();
        whitespace();
        if (pos_ != text_.size()) throw DataError("Datos extras en JSON");
        return result;
    }
    std::map<std::string, Rows> parse() {
        std::map<std::string, Rows> result;
        expect('{');
        if (!consume('}')) {
            do {
                std::string key = string();
                expect(':');
                if (!result.emplace(key, rows()).second) throw DataError("Clave JSON duplicada");
            } while (consume(','));
            expect('}');
        }
        whitespace();
        if (pos_ != text_.size()) throw DataError("Datos extras en JSON");
        return result;
    }
};

int entityIndex(const std::string& kind) {
    auto found = std::find(ENTITY_KINDS.begin(), ENTITY_KINDS.end(), kind);
    return found == ENTITY_KINDS.end() ? -1 : static_cast<int>(found - ENTITY_KINDS.begin());
}
int relationIndex(const std::string& kind) {
    auto found = std::find(RELATION_KINDS.begin(), RELATION_KINDS.end(), kind);
    return found == RELATION_KINDS.end() ? -1 : static_cast<int>(found - RELATION_KINDS.begin());
}
struct Statistics {
    Rows products;
    std::size_t total = 0;
    std::map<std::string, int> byYear;
    std::map<std::string, int> byType;
    std::map<std::string, int> byCategory;
    std::map<std::string, int> byValidation;
};
struct ImportResult {
    std::size_t total = 0;
    std::size_t accepted = 0;
    std::vector<std::string> errors;
};
std::string jsonRows(const Rows& rows);

class Repository {
    std::array<DoublyList, 4> entities_;
    std::array<MultiList, 3> relations_;
    // Los nodos siguen siendo la fuente de verdad; este indice evita barridos por duplicado.
    std::array<std::unordered_map<std::string, std::string>, 4> externalIndex_;
    LinkedQueue queue_;
    std::unordered_map<std::string, std::size_t> queueProductCounts_;
    std::set<std::string> queueIds_;
    LinkedStack history_;
    bool dirty_ = false;

    static Row undoRow(const std::string& op, const std::string& kind, Row row) {
        row["__op"] = op;
        row["__kind"] = kind;
        return row;
    }
    void remember(Rows changes) {
        history_.push("{\"__undo\":" + jsonRows(changes) + "}");
        dirty_ = true;
    }
    void indexJob(const Row& job) {
        const std::string id = field(job, "id");
        if (!queueIds_.insert(id).second) throw DataError("Trabajo de cola duplicado");
        ++queueProductCounts_[field(job, "producto_id")];
    }
    void unindexJob(const Row& job) {
        queueIds_.erase(field(job, "id"));
        const std::string product = field(job, "producto_id");
        auto found = queueProductCounts_.find(product);
        if (found != queueProductCounts_.end() && --found->second == 0)
            queueProductCounts_.erase(found);
    }
    static Rows parseUndo(const std::string& state) {
        auto parsed = SnapshotParser(state).parse();
        if (parsed.size() != 1 || !parsed.count("__undo")) throw DataError("Historial de cambios invalido");
        Rows changes = std::move(parsed.at("__undo"));
        if (changes.empty()) throw DataError("Historial de cambios vacio");
        for (const Row& change : changes) {
            const std::string op = field(change, "__op");
            const std::string kind = field(change, "__kind");
            if (op == "queue_remove") {
                if (field(change, "id").empty()) throw DataError("Historial de cola invalido");
            } else if (op == "queue_prepend") {
                for (const auto& name : {"id", "producto_id", "motivo", "creado"})
                    if (!change.count(name)) throw DataError("Historial de cola invalido");
            } else if (FIELDS.count(kind) && (op == "create" || op == "replace")) {
                Row row = change;
                row.erase("__op");
                row.erase("__kind");
                if (kind == "grupos") row.erase("sigla");
                cleanRow(kind, row);
            } else if (FIELDS.count(kind) && op == "delete") {
                if (entityIndex(kind) >= 0 ? field(change, "id").empty() :
                    (field(change, RELATION_ENDS.at(kind)[0]).empty() ||
                     field(change, RELATION_ENDS.at(kind)[1]).empty()))
                    throw DataError("Historial sin clave");
            } else throw DataError("Operacion de historial desconocida");
        }
        return changes;
    }
    void applyUndo(const Rows& changes) {
        for (const Row& change : changes) {
            const std::string op = field(change, "__op");
            const std::string kind = field(change, "__kind");
            if (op == "queue_remove") {
                Row removed = queue_.remove(field(change, "id"));
                unindexJob(removed);
                continue;
            }
            if (op == "queue_prepend") {
                Row job;
                for (const auto& name : {"id", "producto_id", "motivo", "creado"})
                    job[name] = field(change, name);
                validateJob(job);
                if (queueIds_.count(field(job, "id"))) throw DataError("Trabajo de cola duplicado");
                queue_.prepend(std::move(job));
                indexJob(*queue_.peek());
                continue;
            }
            const auto relation = RELATION_ENDS.find(kind);
            const std::string key = relation == RELATION_ENDS.end() ? field(change, "id") :
                                    field(change, relation->second[0]);
            const std::string second = relation == RELATION_ENDS.end() ? "" :
                                       field(change, relation->second[1]);
            if (op == "delete") erase(kind, key, second, false);
            else {
                Row row = change;
                row.erase("__op");
                row.erase("__kind");
                if (kind == "grupos") row.erase("sigla");
                row = cleanRow(kind, row);
                if (op == "create") create(kind, row, false);
                else {
                    Row* current = get(kind, key, second);
                    if (!current) throw DataError("Registro de historial no encontrado");
                    checkExternal(kind, row, key);
                    if (entityIndex(kind) >= 0) reindexExternal(kind, current, &row);
                    *current = std::move(row);
                }
            }
        }
        dirty_ = true;
    }
    void checkLinks(const std::string& kind, const Row& row) const {
        if (kind == "planes" && !get("grupos", field(row, "grupo_id")))
            throw DataError("El grupo del plan no existe");
        auto found = RELATION_ENDS.find(kind);
        if (found != RELATION_ENDS.end()) {
            const auto& ends = found->second;
            if (!get(ends[2], field(row, ends[0])) || !get(ends[3], field(row, ends[1])))
                throw DataError("La relacion apunta a una entidad inexistente");
        }
    }
    void checkExternal(const std::string& kind, const Row& row, const std::string& oldId) const {
        const std::string name = externalField(kind);
        if (name.empty() || field(row, name).empty()) return;
        const auto normalized = normalizedExternal(kind, field(row, name));
        const auto& index = externalIndex_[static_cast<std::size_t>(entityIndex(kind))];
        auto found = index.find(normalized);
        if (found != index.end() && found->second != oldId)
            throw DataError(label(name) + " ya registrado en " + found->second);
    }
    void reindexExternal(const std::string& kind, const Row* oldRow, const Row* newRow) {
        const std::string name = externalField(kind);
        if (name.empty()) return;
        auto& index = externalIndex_[static_cast<std::size_t>(entityIndex(kind))];
        const std::string oldKey = oldRow && !field(*oldRow, name).empty() ?
                                   normalizedExternal(kind, field(*oldRow, name)) : "";
        const std::string newKey = newRow && !field(*newRow, name).empty() ?
                                   normalizedExternal(kind, field(*newRow, name)) : "";
        if (oldKey == newKey) return;
        if (!newKey.empty()) index.emplace(newKey, field(*newRow, "id"));
        if (!oldKey.empty()) index.erase(oldKey);
    }
    void validateJob(const Row& job) const {
        const std::set<std::string> expected = {"id", "producto_id", "motivo", "creado"};
        std::set<std::string> actual;
        for (const auto& item : job) actual.insert(item.first);
        if (actual != expected || field(job, "id").empty() || field(job, "creado").empty())
            throw DataError("Trabajo de cola incompleto o invalido");
        if (!get("productos", field(job, "producto_id")))
            throw DataError("La cola referencia un producto inexistente");
    }
public:
    Repository()
        : relations_{MultiList("grupo_id", "investigador_id"),
                     MultiList("producto_id", "investigador_id"),
                     MultiList("grupo_id", "producto_id")} {}
    Repository(const Repository&) = delete;
    Repository& operator=(const Repository&) = delete;
    Repository(Repository&&) noexcept = default;
    Repository& operator=(Repository&&) noexcept = default;
    bool dirty() const { return dirty_; }
    void markSaved() { dirty_ = false; }
    std::size_t historySize() const { return history_.size(); }
    std::size_t queueSize() const { return queue_.size(); }
    std::optional<Row> queueFront() const {
        if (const Row* row = queue_.peek()) return *row;
        return std::nullopt;
    }
    Rows queueRows() const { return queue_.rows(); }
    Page queuePage(std::size_t offset, std::size_t limit) const { return queue_.page(offset, limit); }
    void forEachQueue(const std::function<void(const Row&)>& visit) const { queue_.forEach(visit); }
    std::vector<std::string> historyValues() const { return history_.values(); }
    void forEachHistory(const std::function<void(const std::string&)>& visit) const {
        history_.forEach(visit);
    }
    void pushHistory(std::string state) { history_.push(std::move(state)); dirty_ = true; }
    void pushUndo(const Rows& changes) {
        if (!changes.empty()) {
            history_.push("{\"__undo\":" + jsonRows(changes) + "}");
            dirty_ = true;
        }
    }
    void clearHistory() { history_.clear(); dirty_ = true; }

    Row* get(const std::string& kind, const std::string& key,
             const std::string& second = "") const {
        int entity = entityIndex(kind);
        if (entity >= 0) return entities_[static_cast<std::size_t>(entity)].get(key);
        int relation = relationIndex(kind);
        if (relation >= 0) return relations_[static_cast<std::size_t>(relation)].get(key, second);
        return nullptr;
    }
    Rows rows(const std::string& kind) const {
        int entity = entityIndex(kind);
        if (entity >= 0) return entities_[static_cast<std::size_t>(entity)].rows();
        int relation = relationIndex(kind);
        if (relation >= 0) return relations_[static_cast<std::size_t>(relation)].rows();
        throw DataError("Tipo desconocido: " + kind);
    }
    void forEachRow(const std::string& kind, const std::function<void(const Row&)>& visit) const {
        int entity = entityIndex(kind);
        if (entity >= 0) { entities_[static_cast<std::size_t>(entity)].forEach(visit); return; }
        int relation = relationIndex(kind);
        if (relation >= 0) { relations_[static_cast<std::size_t>(relation)].forEach(visit); return; }
        throw DataError("Tipo desconocido: " + kind);
    }
    Page page(const std::string& kind, std::size_t offset, std::size_t limit,
              const std::string& query) const {
        const std::string normalized = lowercase(trim(query));
        int entity = entityIndex(kind);
        if (entity >= 0) return entities_[static_cast<std::size_t>(entity)].page(offset, limit, normalized);
        int relation = relationIndex(kind);
        if (relation >= 0) return relations_[static_cast<std::size_t>(relation)].page(offset, limit, normalized);
        throw DataError("Tipo desconocido: " + kind);
    }
    std::pair<std::size_t, std::size_t> activeCounts() const {
        return {entities_[0].activeCount(), entities_[1].activeCount()};
    }
    Rows related(const std::string& kind, const std::string& id, bool fromLeft) const {
        int relation = relationIndex(kind);
        if (relation < 0) throw DataError("Relacion desconocida: " + kind);
        const auto& list = relations_[static_cast<std::size_t>(relation)];
        return fromLeft ? list.byLeft(id) : list.byRight(id);
    }
    Page relatedPage(const std::string& kind, const std::string& id, bool fromLeft,
                     std::size_t offset, std::size_t limit, bool activeOnly = false) const {
        int relation = relationIndex(kind);
        if (relation < 0) throw DataError("Relacion desconocida: " + kind);
        return relations_[static_cast<std::size_t>(relation)].relatedPage(id, fromLeft, offset, limit, activeOnly);
    }
    void forEachRelated(const std::string& kind, const std::string& id, bool fromLeft,
                        const std::function<void(const Row&)>& visit) const {
        int relation = relationIndex(kind);
        if (relation < 0) throw DataError("Relacion desconocida: " + kind);
        relations_[static_cast<std::size_t>(relation)].forEachRelated(id, fromLeft, visit);
    }
    Row validateCreate(const std::string& kind, const Row& values) const {
        Row row = cleanRow(kind, values);
        checkLinks(kind, row);
        int entity = entityIndex(kind);
        if (entity >= 0) {
            checkExternal(kind, row, "");
            if (get(kind, field(row, "id"))) throw DataError("ID duplicado");
        } else {
            auto found = RELATION_ENDS.find(kind);
            if (found == RELATION_ENDS.end()) throw DataError("Tipo desconocido: " + kind);
            if (get(kind, field(row, found->second[0]), field(row, found->second[1])))
                throw DataError("Relacion duplicada");
        }
        return row;
    }
    void create(const std::string& kind, const Row& values, bool withUndo = true) {
        Row row = validateCreate(kind, values);
        const int entity = entityIndex(kind);
        if (withUndo) {
            Row key = entity >= 0 ? Row{{"id", field(row, "id")}} :
                Row{{RELATION_ENDS.at(kind)[0], field(row, RELATION_ENDS.at(kind)[0])},
                    {RELATION_ENDS.at(kind)[1], field(row, RELATION_ENDS.at(kind)[1])}};
            remember({undoRow("delete", kind, std::move(key))});
        }
        if (entity >= 0) {
            const std::string id = field(row, "id");
            entities_[static_cast<std::size_t>(entity)].append(std::move(row));
            try { reindexExternal(kind, nullptr, get(kind, id)); }
            catch (...) {
                entities_[static_cast<std::size_t>(entity)].erase(id);
                throw;
            }
        } else relations_[static_cast<std::size_t>(relationIndex(kind))].add(std::move(row));
    }
    void update(const std::string& kind, const std::string& key, const std::string& second,
                const Row& changes, bool withUndo = true) {
        Row* current = get(kind, key, second);
        if (!current) throw DataError("Registro no encontrado");
        Row merged = *current;
        for (const auto& item : changes) merged[item.first] = item.second;
        Row updated = cleanRow(kind, merged);
        if (entityIndex(kind) >= 0) {
            if (field(updated, "id") != field(*current, "id"))
                throw DataError("El ID es estable");
            checkExternal(kind, updated, field(*current, "id"));
        } else {
            const auto& ends = RELATION_ENDS.at(kind);
            if (field(updated, ends[0]) != field(*current, ends[0]) ||
                field(updated, ends[1]) != field(*current, ends[1]))
                throw DataError("Los extremos son estables; cree otra relacion");
        }
        checkLinks(kind, updated);
        if (kind == "productos" &&
            (field(updated, "categoria") != field(*current, "categoria") ||
             field(updated, "validacion") != field(*current, "validacion")) &&
            (field(updated, "observacion").empty() ||
             field(updated, "observacion") == field(*current, "observacion")))
            throw DataError("Explique el cambio de categoria o validacion en Observacion");
        if (withUndo) remember({undoRow("replace", kind, *current)});
        if (entityIndex(kind) >= 0) reindexExternal(kind, current, &updated);
        *current = std::move(updated);
        dirty_ = true;
    }
    void erase(const std::string& kind, const std::string& key,
               const std::string& second = "", bool withUndo = true) {
        if (!get(kind, key, second)) throw DataError("Registro no encontrado");
        const int entity = entityIndex(kind);
        if (entity >= 0) {
            if (kind == "grupos") {
                forEachRow("planes", [&](const Row& plan) {
                    if (field(plan, "grupo_id") == key)
                        throw DataError("El grupo tiene planes; eliminelos o desactivelo");
                });
            }
            for (const auto& relKind : RELATION_KINDS) {
                const auto& ends = RELATION_ENDS.at(relKind);
                if (ends[2] != kind && ends[3] != kind) continue;
                if (relatedPage(relKind, key, ends[2] == kind, 0, 0).total)
                    throw DataError("Hay relaciones asociadas; eliminelas o desactive el registro");
            }
            if (kind == "productos" && queueProductCounts_.count(key))
                throw DataError("Hay revisiones pendientes para el producto");
        }
        if (withUndo) remember({undoRow("create", kind, *get(kind, key, second))});
        if (entity >= 0) {
            reindexExternal(kind, get(kind, key), nullptr);
            entities_[static_cast<std::size_t>(entity)].erase(key);
        }
        else relations_[static_cast<std::size_t>(relationIndex(kind))].erase(key, second);
        dirty_ = true;
    }
    void toggle(const std::string& kind, const std::string& key, const std::string& second = "") {
        Row* row = get(kind, key, second);
        if (!row) throw DataError("Registro no encontrado");
        update(kind, key, second, {{"activo", field(*row, "activo") == "1" ? "0" : "1"}});
    }
    std::string snapshot() const {
        std::string output = "{";
        bool firstKind = true;
        auto addRows = [&](const std::string& kind, const Rows& source,
                           const std::vector<std::string>& columns) {
            if (!firstKind) output.push_back(',');
            firstKind = false;
            output += jsonString(kind) + ":[";
            bool firstRow = true;
            for (const Row& row : source) {
                if (!firstRow) output.push_back(',');
                firstRow = false;
                output.push_back('{');
                for (std::size_t i = 0; i < columns.size(); ++i) {
                    if (i) output.push_back(',');
                    output += jsonString(columns[i]) + ":" + jsonString(field(row, columns[i]));
                }
                output.push_back('}');
            }
            output.push_back(']');
        };
        for (const auto& kind : ALL_KINDS) addRows(kind, rows(kind), FIELDS.at(kind));
        addRows("cola_validacion", queue_.rows(), {"id", "producto_id", "motivo", "creado"});
        output.push_back('}');
        return output;
    }
    void restore(const std::string& state) {
        auto parsed = SnapshotParser(state).parse();
        if ((parsed.size() != ALL_KINDS.size() + 1 || !parsed.count("cola_validacion")) &&
            parsed.size() != ALL_KINDS.size())
            throw DataError("Historial incompleto");
        Repository fresh;
        for (const auto& kind : ENTITY_KINDS) {
            if (!parsed.count(kind)) throw DataError("Historial sin " + kind);
            for (Row row : parsed.at(kind)) {
                if (kind == "grupos") row.erase("sigla");
                fresh.create(kind, row, false);
            }
        }
        for (const auto& kind : RELATION_KINDS) {
            if (!parsed.count(kind)) throw DataError("Historial sin " + kind);
            for (const Row& row : parsed.at(kind)) fresh.create(kind, row, false);
        }
        if (parsed.count("cola_validacion"))
            for (const Row& job : parsed.at("cola_validacion")) fresh.loadJob(job);
        entities_ = std::move(fresh.entities_);
        relations_ = std::move(fresh.relations_);
        externalIndex_ = std::move(fresh.externalIndex_);
        queue_ = std::move(fresh.queue_);
        queueProductCounts_ = std::move(fresh.queueProductCounts_);
        queueIds_ = std::move(fresh.queueIds_);
        dirty_ = true;
    }
    bool undo() {
        auto state = history_.peek();
        if (!state) return false;
        if (startsWith(*state, "{\"__undo\":"))
            applyUndo(parseUndo(*state));
        else restore(*state);
        history_.pop();
        return true;
    }
    void loadQueue(const Rows& jobs) {
        for (const Row& job : jobs) loadJob(job);
    }
    void loadJob(const Row& job) {
        validateJob(job);
        if (queueIds_.count(field(job, "id"))) throw DataError("Trabajo de cola duplicado");
        queue_.enqueue(job);
        indexJob(job);
    }
    void loadHistory(const Rows& entries) {
        for (auto it = entries.rbegin(); it != entries.rend(); ++it) {
            const std::string state = field(*it, "snapshot");
            if (startsWith(state, "{\"__undo\":")) parseUndo(state);
            else { Repository check; check.restore(state); }
            history_.push(state);
        }
    }
    void enqueueReview(const std::string& productId, const std::string& reason) {
        if (!get("productos", productId)) throw DataError("Producto inexistente");
        if (queueProductCounts_.count(productId)) throw DataError("El producto ya esta en la cola");
        static std::uint64_t counter = 0;
        const auto ticks = std::chrono::high_resolution_clock::now().time_since_epoch().count();
        Row job = {{"id", "Q-" + std::to_string(ticks) + "-" + std::to_string(++counter)},
                   {"producto_id", productId}, {"motivo", trim(reason)}, {"creado", nowIso()}};
        remember({undoRow("queue_remove", "", {{"id", field(job, "id")}})});
        queue_.enqueue(std::move(job));
        indexJob(*queue_.back());
        dirty_ = true;
    }
    Row processReview(const std::string& status, const std::string& observation) {
        const Row* job = queue_.peek();
        if (!job) throw DataError("La cola esta vacia");
        if (status != "validado" && status != "rechazado" && status != "pendiente")
            throw DataError("Estado invalido");
        if (trim(observation).empty()) throw DataError("Debe registrar una observacion");
        Row* product = get("productos", field(*job, "producto_id"));
        if (!product) throw DataError("Producto inexistente");
        if (field(*product, "validacion") != status && field(*product, "observacion") == trim(observation))
            throw DataError("Escriba una observacion nueva");
        cleanRow("productos", [&] {
            Row proposed = *product;
            proposed["validacion"] = status;
            proposed["observacion"] = observation;
            return proposed;
        }());
        remember({undoRow("replace", "productos", *product),
                  undoRow("queue_prepend", "", *job)});
        Row completed = *job;
        update("productos", field(*job, "producto_id"), "", {{"validacion", status}, {"observacion", observation}}, false);
        unindexJob(*queue_.dequeue());
        dirty_ = true;
        return completed;
    }
    Row discardReview() {
        if (!queue_.peek()) throw DataError("La cola esta vacia");
        remember({undoRow("queue_prepend", "", *queue_.peek())});
        Row value = *queue_.dequeue();
        unindexJob(value);
        dirty_ = true;
        return value;
    }
    Statistics statistics(const std::string& view = "Todos", const std::string& selectedId = "",
                          std::optional<int> start = {}, std::optional<int> end = {},
                          const std::string& category = "", const std::string& status = "",
                          std::size_t offset = 0, std::size_t limit = SIZE_MAX) const {
        // Hipercubo logico: el producto es el hecho; grupo e investigador se
        // recorren por multilistas. Anio, tipologia, categoria y validacion son
        // dimensiones consultables. La vista selecciona una dimension relacional
        // y los agregados se calculan al consultar, sin materializar un cubo OLAP
        // ni cruzar grupo e investigador simultaneamente.
        if (view != "Todos" && view != "Grupo" && view != "Investigador" && view != "Producto")
            throw DataError("Vista desconocida");
        if (start && end && *start > *end) throw DataError("El anio inicial supera al final");
        std::optional<std::set<std::string>> selected;
        if (view == "Grupo") {
            selected.emplace();
            forEachRelated("grupos_productos", selectedId, true, [&](const Row& rel) {
                if (field(rel, "activo") == "1") selected->insert(field(rel, "producto_id"));
            });
        } else if (view == "Investigador") {
            selected.emplace();
            forEachRelated("autorias", selectedId, false, [&](const Row& rel) {
                if (field(rel, "activo") == "1") selected->insert(field(rel, "producto_id"));
            });
        } else if (view == "Producto") {
            selected.emplace();
            if (!selectedId.empty()) selected->insert(selectedId);
        }
        Statistics result;
        entities_[2].forEach([&](const Row& product) {
            if (field(product, "activo") != "1") return;
            if (selected && !selected->count(field(product, "id"))) return;
            const std::string yearText = field(product, "anio");
            if ((start || end) && yearText.empty()) return;
            if (start && std::stoi(yearText) < *start) return;
            if (end && std::stoi(yearText) > *end) return;
            if (!category.empty() && field(product, "categoria") != category) return;
            if (!status.empty() && field(product, "validacion") != status) return;
            if (result.total >= offset && result.products.size() < limit)
                result.products.push_back(product);
            ++result.total;
            auto count = [&](std::map<std::string, int>& tally, const std::string& name) {
                const auto& text = field(product, name);
                ++tally[text.empty() ? "Sin dato" : text];
            };
            count(result.byYear, "anio");
            count(result.byType, "tipologia");
            count(result.byCategory, "categoria");
            count(result.byValidation, "validacion");
        });
        return result;
    }
};

const std::vector<std::string> MANIFEST_FIELDS = {"version", "guardado"};
const std::vector<std::string> QUEUE_FIELDS = {"id", "producto_id", "motivo", "creado"};
const std::vector<std::string> HISTORY_FIELDS = {"orden", "snapshot"};
std::vector<std::string> dataFiles() {
    std::vector<std::string> result = {"manifest.csv"};
    for (const auto& kind : ALL_KINDS) result.push_back(kind + ".csv");
    result.push_back("cola_validacion.csv");
    result.push_back("historial.csv");
    return result;
}
bool headerMatches(const fs::path& path, const std::vector<std::string>& fields) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw DataError("No se pudo abrir " + path.string());
    std::string first;
    std::getline(input, first);
    if (startsWith(first, "\xef\xbb\xbf")) first.erase(0, 3);
    if (!first.empty() && first.back() == '\r') first.pop_back();
    std::string expected;
    for (std::size_t i = 0; i < fields.size(); ++i)
        expected += (i ? "," : "") + fields[i];
    return first == expected;
}
Repository loadRepository(const fs::path& directory) {
    std::string version;
    std::size_t manifestRows = 0;
    readCsvEach(directory / "manifest.csv", MANIFEST_FIELDS,
                [&](Row row, std::size_t) {
        if (++manifestRows > 1) throw DataError("Manifest con mas de una fila");
        version = field(row, "version");
    });
    if (manifestRows != 1 || (version != "1" && version != "2"))
        throw DataError("Version de datos incompatible");
    const bool legacy = version == "1";
    Repository repo;
    for (const auto& kind : ENTITY_KINDS) {
        auto columns = FIELDS.at(kind);
        const fs::path path = directory / (kind + ".csv");
        if (legacy && kind == "grupos") {
            auto oldColumns = columns;
            oldColumns.insert(oldColumns.begin() + 2, "sigla");
            if (headerMatches(path, oldColumns)) columns = std::move(oldColumns);
        }
        if (legacy && kind == "productos") {
            auto oldColumns = columns;
            oldColumns.erase(std::remove(oldColumns.begin(), oldColumns.end(), "validacion"), oldColumns.end());
            if (headerMatches(path, oldColumns)) columns = std::move(oldColumns);
        }
        readCsvEach(path, columns,
                    [&](Row row, std::size_t number) {
            try {
                if (legacy && kind == "grupos") row.erase("sigla");
                repo.create(kind, row, false);
            }
            catch (const DataError& error) {
                throw DataError(kind + ".csv, fila " + std::to_string(number) + ": " + error.what());
            }
        }, !legacy);
    }
    for (const auto& kind : RELATION_KINDS) {
        readCsvEach(directory / (kind + ".csv"), FIELDS.at(kind),
                    [&](Row row, std::size_t number) {
            try { repo.create(kind, row, false); }
            catch (const DataError& error) {
                throw DataError(kind + ".csv, fila " + std::to_string(number) + ": " + error.what());
            }
        }, !legacy);
    }
    const fs::path queuePath = directory / "cola_validacion.csv";
    if (!legacy || fs::exists(queuePath)) readCsvEach(queuePath, QUEUE_FIELDS,
                [&](Row job, std::size_t number) {
        try { repo.loadJob(job); }
        catch (const DataError& error) {
            throw DataError("cola_validacion.csv, fila " + std::to_string(number) + ": " + error.what());
        }
    }, !legacy);
    Rows history;
    readCsvEach(directory / "historial.csv", HISTORY_FIELDS,
                [&](Row row, std::size_t) {
        if (history.size() >= 30) throw DataError("Historial supera 30 acciones");
        history.push_back(std::move(row));
    }, !legacy);
    repo.loadHistory(history);
    repo.markSaved();
    return repo;
}
struct StagingFolder {
    fs::path path;
    explicit StagingFolder(fs::path location) : path(std::move(location)) {
        fs::create_directories(path);
    }
    ~StagingFolder() {
        std::error_code ignored;
        fs::remove_all(path, ignored);
    }
};
void saveRepository(Repository& repo, const fs::path& directory) {
    fs::create_directories(directory);
    const auto tick = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    StagingFolder stage(directory / (".pea-stage-" + std::to_string(tick)));
    writeCsv(stage.path / "manifest.csv", MANIFEST_FIELDS,
             {{{"version", "2"}, {"guardado", nowIso()}}});
    for (const auto& kind : ALL_KINDS)
        writeCsvEach(stage.path / (kind + ".csv"), FIELDS.at(kind),
                     [&](const auto& visit) { repo.forEachRow(kind, visit); }, true);
    writeCsvEach(stage.path / "cola_validacion.csv", QUEUE_FIELDS,
                 [&](const auto& visit) { repo.forEachQueue(visit); }, true);
    std::size_t order = 0;
    writeCsvEach(stage.path / "historial.csv", HISTORY_FIELDS,
                 [&](const auto& visit) {
        repo.forEachHistory([&](const std::string& state) {
            visit({{"orden", std::to_string(order++)}, {"snapshot", state}});
        });
    }, true);
    const fs::path backup = directory / ".backup";
    fs::create_directories(backup);
    const auto files = dataFiles();
    for (const auto& name : files) {
        if (fs::exists(directory / name))
            fs::copy_file(directory / name, backup / name, fs::copy_options::overwrite_existing);
    }
    for (const auto& name : files) {
        const fs::path target = directory / name;
        // Windows no permite rename sobre un archivo existente. La copia anterior
        // ya esta en .backup si el proceso se interrumpe entre archivos.
        if (fs::exists(target)) fs::remove(target);
        fs::rename(stage.path / name, target);
    }
    repo.markSaved();
}
ImportResult importCsv(Repository& repo, const fs::path& path, const std::string& kind,
                       bool apply) {
    if (!FIELDS.count(kind)) throw DataError("Tipo de CSV desconocido");
    ImportResult result;
    std::set<std::string> ids;
    std::set<std::pair<std::string, std::string>> pairs;
    std::set<std::string> external;
    readCsvEach(path, FIELDS.at(kind), [&](Row row, std::size_t number) {
        ++result.total;
        try {
            Row clean = repo.validateCreate(kind, row);
            if (entityIndex(kind) >= 0) {
                if (ids.count(field(clean, "id"))) throw DataError("ID duplicado");
                const std::string name = externalField(kind);
                if (!name.empty() && !field(clean, name).empty() &&
                    external.count(normalizedExternal(kind, field(clean, name))))
                    throw DataError(label(name) + " duplicado en el archivo");
                ids.insert(field(clean, "id"));
                if (!name.empty() && !field(clean, name).empty())
                    external.insert(normalizedExternal(kind, field(clean, name)));
            } else {
                const auto& ends = RELATION_ENDS.at(kind);
                const auto pair = std::pair{field(clean, ends[0]), field(clean, ends[1])};
                if (pairs.count(pair))
                    throw DataError("Relacion duplicada");
                pairs.insert(pair);
            }
            ++result.accepted;
        } catch (const DataError& error) {
            if (result.errors.size() < 100)
                result.errors.push_back("Fila " + std::to_string(number) + ": " + error.what());
        }
    });
    if (result.total - result.accepted > result.errors.size())
        result.errors.push_back("Se omitieron mas errores; total rechazadas: " +
                                std::to_string(result.total - result.accepted));
    if (apply && result.accepted) {
        const bool wasDirty = repo.dirty();
        Rows inverse;
        inverse.reserve(result.accepted);
        try {
            readCsvEach(path, FIELDS.at(kind), [&](Row row, std::size_t) {
                try {
                    repo.validateCreate(kind, row);
                } catch (const DataError&) { return; }
                Row change = {{"__op", "delete"}, {"__kind", kind}};
                if (entityIndex(kind) >= 0) change["id"] = trim(field(row, "id"));
                else {
                    const auto& ends = RELATION_ENDS.at(kind);
                    change[ends[0]] = trim(field(row, ends[0]));
                    change[ends[1]] = trim(field(row, ends[1]));
                }
                inverse.push_back(std::move(change));
                try { repo.create(kind, row, false); }
                catch (const DataError&) { inverse.pop_back(); }
            });
            result.accepted = inverse.size();
            repo.pushUndo(inverse);
        } catch (...) {
            for (auto it = inverse.rbegin(); it != inverse.rend(); ++it) {
                const auto& change = *it;
                const auto ends = RELATION_ENDS.find(kind);
                const std::string key = ends == RELATION_ENDS.end() ? field(change, "id") :
                                        field(change, ends->second[0]);
                const std::string second = ends == RELATION_ENDS.end() ? "" :
                                           field(change, ends->second[1]);
                if (repo.get(kind, key, second)) repo.erase(kind, key, second, false);
            }
            if (!wasDirty) repo.markSaved();
            throw;
        }
    }
    return result;
}

struct EndInput {};
std::string ask(const std::string& prompt) {
    std::cout << prompt;
    std::string answer;
    if (!std::getline(std::cin, answer)) throw EndInput{};
    return trim(answer);
}
int askNumber(const std::string& prompt, int low, int high) {
    while (true) {
        std::string value = ask(prompt);
        if (digits(value)) {
            try {
                int number = std::stoi(value);
                if (number >= low && number <= high) return number;
            } catch (const std::exception&) {}
        }
        std::cout << "Ingrese un numero entre " << low << " y " << high << ".\n";
    }
}
bool confirm(const std::string& question) {
    const std::string answer = lowercase(ask(question + " [s/N]: "));
    return answer == "s" || answer == "si";
}
std::string display(std::string text, std::size_t maxLength = 68) {
    for (char& ch : text) if (ch == '\n' || ch == '\r' || ch == '\t') ch = ' ';
    if (text.size() > maxLength) {
        std::size_t end = maxLength > 3 ? maxLength - 3 : 0;
        while (end > 0 && (static_cast<unsigned char>(text[end]) & 0xc0) == 0x80) --end;
        return text.substr(0, end) + "...";
    }
    return text;
}
std::string unescapeNewlines(const std::string& input) {
    std::string result;
    for (std::size_t i = 0; i < input.size(); ++i) {
        if (input[i] == '\\' && i + 1 < input.size() && input[i + 1] == 'n') {
            result.push_back('\n');
            ++i;
        } else result.push_back(input[i]);
    }
    return result;
}
std::string newId(const std::string& kind) {
    const std::string prefix = kind == "grupos" ? "G" :
                               kind == "investigadores" ? "I" :
                               kind == "productos" ? "P" : "PL";
    static std::uint64_t serial = 0;
    const auto tick = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    std::ostringstream out;
    out << prefix << "-" << std::hex << tick << "-" << ++serial;
    return out.str();
}
Row inputRecord(const std::string& kind, const Row* original = nullptr) {
    Row row = original ? *original : Row{};
    const auto& fields = FIELDS.at(kind);
    std::string first;
    std::string second;
    if (relationIndex(kind) >= 0) {
        const auto& ends = RELATION_ENDS.at(kind);
        first = ends[0];
        second = ends[1];
    }
    std::cout << "Escriba \\n para un salto de linea en campos de texto.\n";
    if (original) std::cout << "Enter conserva el valor; :vaciar lo borra.\n";
    for (const auto& name : fields) {
        if (original && (name == "id" || name == first || name == second)) continue;
        std::string defaultValue;
        if (!original && name == "id") defaultValue = newId(kind);
        else if (!original && name == "activo") defaultValue = "1";
        else if (!original && name == "validacion") defaultValue = "pendiente";
        const std::string current = original ? field(*original, name) : defaultValue;
        std::string prompt = label(name);
        if (!current.empty()) prompt += " [" + display(current, 48) + "]";
        prompt += ": ";
        const std::string value = ask(prompt);
        if (original) {
            if (value == ":vaciar") row[name] = "";
            else if (!value.empty()) row[name] = unescapeNewlines(value);
        } else {
            row[name] = value.empty() ? defaultValue : unescapeNewlines(value);
        }
    }
    return row;
}
std::pair<std::string, std::string> askKey(const std::string& kind) {
    if (entityIndex(kind) >= 0) return {ask("ID: "), ""};
    const auto& ends = RELATION_ENDS.at(kind);
    return {ask(label(ends[0]) + ": "), ask(label(ends[1]) + ": ")};
}
std::string nameField(const std::string& kind) {
    if (kind == "productos") return "titulo";
    if (kind == "membresias" || kind == "autorias") return "rol";
    if (kind == "grupos_productos") return "origen";
    return "nombre";
}
void printListing(const Repository& repo, const std::string& kind) {
    const std::string query = lowercase(ask("Buscar (Enter para todos): "));
    const Page page = repo.page(kind, 0, 40, query);
    const bool relation = relationIndex(kind) >= 0;
    if (relation) {
        const auto& ends = RELATION_ENDS.at(kind);
        std::cout << label(ends[0]) << " | " << label(ends[1]) << " | "
                  << label(nameField(kind)) << " | Activo\n";
    } else {
        std::cout << "ID | " << label(nameField(kind)) << " | Activo\n";
    }
    for (const Row& row : page.rows) {
        if (relation) {
            const auto& ends = RELATION_ENDS.at(kind);
            std::cout << display(field(row, ends[0]), 26) << " | "
                      << display(field(row, ends[1]), 26) << " | ";
        } else std::cout << display(field(row, "id"), 26) << " | ";
        std::cout << display(field(row, nameField(kind)), 60)
                  << " | " << field(row, "activo") << '\n';
    }
    std::cout << "Coincidencias: " << page.total;
    if (page.total > 40) std::cout << " (primeras 40 mostradas)";
    std::cout << '\n';
}
void printDetail(const Repository& repo, const std::string& kind,
                 const std::string& key, const std::string& second) {
    const Row* row = repo.get(kind, key, second);
    if (!row) throw DataError("Registro no encontrado");
    std::cout << "\n";
    for (const auto& name : FIELDS.at(kind))
        std::cout << label(name) << ": " << field(*row, name) << '\n';
    auto printRelated = [&](const std::string& title, const std::string& relKind,
                            const std::string& id, bool fromLeft,
                            const std::string& otherField, const std::string& targetKind) {
        const Page links = repo.relatedPage(relKind, id, fromLeft, 0, 40);
        std::cout << "\n" << title << " (" << links.total << "):\n";
        for (const Row& link : links.rows) {
            const std::string otherId = field(link, otherField);
            const Row* other = repo.get(targetKind, otherId);
            std::cout << "- " << otherId << ": "
                      << (other ? display(field(*other, nameField(targetKind)), 75) : "(sin registro)")
                      << " [" << (field(link, "activo") == "1" ? "activo" : "inactivo") << "]\n";
        }
        if (links.total > links.rows.size()) std::cout << "(primeras 40 mostradas)\n";
    };
    if (kind == "grupos") {
        printRelated("Integrantes", "membresias", key, true, "investigador_id", "investigadores");
        printRelated("Productos", "grupos_productos", key, true, "producto_id", "productos");
        std::cout << "\nPlanes:\n";
        repo.forEachRow("planes", [&](const Row& plan) {
            if (field(plan, "grupo_id") == key)
                std::cout << "- " << field(plan, "id") << ": " << field(plan, "nombre") << '\n';
        });
    } else if (kind == "investigadores") {
        printRelated("Grupos", "membresias", key, false, "grupo_id", "grupos");
        printRelated("Productos", "autorias", key, false, "producto_id", "productos");
    } else if (kind == "productos") {
        printRelated("Autores", "autorias", key, true, "investigador_id", "investigadores");
        printRelated("Grupos", "grupos_productos", key, false, "grupo_id", "grupos");
    }
}
void recordMenu(Repository& repo, const std::string& kind) {
    while (true) {
        std::cout << "\n=== " << kind << " ===\n"
                  << "1. Listar/buscar  2. Consultar  3. Crear  4. Editar\n"
                  << "5. Activar/desactivar  6. Eliminar  0. Volver\n";
        const int option = askNumber("Opcion: ", 0, 6);
        if (option == 0) return;
        try {
            if (option == 1) {
                printListing(repo, kind);
            } else if (option == 3) {
                repo.create(kind, inputRecord(kind));
                std::cout << "Registro creado. Guarde para conservarlo.\n";
            } else {
                const auto [key, second] = askKey(kind);
                if (option == 2) {
                    printDetail(repo, kind, key, second);
                } else if (option == 4) {
                    const Row* current = repo.get(kind, key, second);
                    if (!current) throw DataError("Registro no encontrado");
                    repo.update(kind, key, second, inputRecord(kind, current));
                    std::cout << "Registro actualizado.\n";
                } else if (option == 5) {
                    repo.toggle(kind, key, second);
                    std::cout << "Estado cambiado.\n";
                } else if (option == 6 && confirm("Eliminar definitivamente?")) {
                    repo.erase(kind, key, second);
                    std::cout << "Registro eliminado.\n";
                }
            }
        } catch (const std::exception& error) {
            std::cout << "Error: " << error.what() << '\n';
        }
    }
}
void relationMenu(Repository& repo) {
    while (true) {
        std::cout << "\n=== Relaciones ===\n"
                  << "1. Integrantes de grupos  2. Autorias  3. Grupos-productos  0. Volver\n";
        const int option = askNumber("Opcion: ", 0, 3);
        if (option == 0) return;
        recordMenu(repo, RELATION_KINDS[static_cast<std::size_t>(option - 1)]);
    }
}

void printTally(const std::string& title, const std::map<std::string, int>& values) {
    std::cout << "\n" << title << ":\n";
    if (values.empty()) { std::cout << "  Sin datos\n"; return; }
    for (const auto& item : values)
        std::cout << "  " << display(item.first, 58) << " | " << item.second << '\n';
}
void statisticsMenu(const Repository& repo) {
    std::cout << "\n=== Estadisticas descriptivas ===\n"
              << "1. Todos  2. Por grupo  3. Por investigador  4. Por producto\n";
    const int viewOption = askNumber("Vista: ", 1, 4);
    const std::array<std::string, 4> views = {"Todos", "Grupo", "Investigador", "Producto"};
    const std::string view = views[static_cast<std::size_t>(viewOption - 1)];
    std::string selected;
    if (viewOption != 1) selected = ask(view + " ID: ");
    std::cout << "1. Todos los anios  2. Ultimos 2  3. Ultimos 5  4. Rango\n";
    const int window = askNumber("Ventana: ", 1, 4);
    std::optional<int> start;
    std::optional<int> end;
    if (window == 2 || window == 3) {
        end = currentYear();
        start = *end - (window == 2 ? 2 : 5) + 1;
    } else if (window == 4) {
        const std::string from = ask("Desde (vacio = sin limite): ");
        const std::string to = ask("Hasta (vacio = sin limite): ");
        auto parse = [](const std::string& text) -> std::optional<int> {
            if (text.empty()) return std::nullopt;
            if (!digits(text)) throw DataError("Anio invalido");
            const int value = std::stoi(text);
            if (value < 1900 || value > currentYear() + 1) throw DataError("Anio fuera de rango");
            return value;
        };
        start = parse(from);
        end = parse(to);
    }
    const std::string category = ask("Categoria exacta (vacio = todas): ");
    const std::string validation = ask("Validacion exacta (vacio = todas): ");
    const Statistics stats = repo.statistics(view, selected, start, end, category, validation, 0, 40);
    const auto [activeGroups, activePeople] = repo.activeCounts();
    std::cout << "\nVista: " << view;
    if (!selected.empty()) std::cout << " " << selected;
    std::cout << "\nProductos unicos: " << stats.total
              << "\nGrupos activos: " << activeGroups
              << "\nInvestigadores activos: " << activePeople << '\n';
    printTally("Por anio", stats.byYear);
    printTally("Por tipologia", stats.byType);
    printTally("Por categoria", stats.byCategory);
    printTally("Por validacion", stats.byValidation);
    std::cout << "\nProductos (ID | Anio | Titulo | Categoria | Validacion):\n";
    std::size_t shown = 0;
    for (const Row& row : stats.products) {
        if (++shown > 40) break;
        std::cout << display(field(row, "id"), 22) << " | " << field(row, "anio")
                  << " | " << display(field(row, "titulo"), 48)
                  << " | " << display(field(row, "categoria"), 24)
                  << " | " << field(row, "validacion") << '\n';
    }
    if (stats.total > 40) std::cout << "(primeros 40 mostrados)\n";
    std::cout << "Cada producto se cuenta una vez; el filtro temporal excluye anios sin dato.\n";
}
void queueMenu(Repository& repo) {
    while (true) {
        std::cout << "\n=== Cola de revision FIFO ===\n"
                  << "1. Ver pendientes  2. Encolar producto  3. Procesar frente\n"
                  << "4. Descartar frente  0. Volver\n";
        const int option = askNumber("Opcion: ", 0, 4);
        if (option == 0) return;
        try {
            if (option == 1) {
                const Page jobs = repo.queuePage(0, 40);
                std::cout << "Pendientes: " << jobs.total << '\n';
                for (const Row& job : jobs.rows)
                    std::cout << field(job, "id") << " | " << field(job, "producto_id")
                              << " | " << display(field(job, "motivo"), 65)
                              << " | " << field(job, "creado") << '\n';
                if (jobs.total > jobs.rows.size()) std::cout << "(primeras 40 mostradas)\n";
            } else if (option == 2) {
                const std::string id = ask("Producto ID: ");
                const std::string reason = ask("Motivo: ");
                repo.enqueueReview(id, reason);
                std::cout << "Revision encolada.\n";
            } else {
                auto job = repo.queueFront();
                if (!job) throw DataError("La cola esta vacia");
                std::cout << "Frente: " << field(*job, "producto_id") << " - "
                          << field(*job, "motivo") << '\n';
                if (option == 3) {
                    const std::string status = lowercase(ask("Estado (validado/rechazado/pendiente): "));
                    const std::string observation = ask("Observacion nueva: ");
                    const Row completed = repo.processReview(status, observation);
                    std::cout << "Procesado " << field(completed, "producto_id") << ".\n";
                } else if (confirm("Descartar esta revision?")) {
                    repo.discardReview();
                    std::cout << "Revision retirada.\n";
                }
            }
        } catch (const std::exception& error) {
            std::cout << "Error: " << error.what() << '\n';
        }
    }
}
fs::path projectDemo() {
    fs::path cursor = fs::current_path();
    for (int i = 0; i < 6; ++i) {
        fs::path candidate = cursor / "data" / "demo";
        if (fs::exists(candidate / "manifest.csv")) return candidate;
        if (!cursor.has_parent_path() || cursor.parent_path() == cursor) break;
        cursor = cursor.parent_path();
    }
    return {};
}
bool samePath(const fs::path& a, const fs::path& b) {
    if (a.empty() || b.empty()) return false;
    std::error_code ignored;
    return fs::weakly_canonical(a, ignored) == fs::weakly_canonical(b, ignored);
}
class ConsoleApp {
    Repository repo_;
    fs::path directory_;
    fs::path demoPath_ = projectDemo();
    bool demo_ = false;

    bool saveTo(const fs::path& path) {
        if (path.empty()) return false;
        if (samePath(path, demoPath_)) {
            std::cout << "La demostracion es de solo lectura; elija otra carpeta.\n";
            return false;
        }
        if (fs::exists(path / "manifest.csv") && !samePath(path, directory_) &&
            !confirm("La carpeta ya contiene datos PEA-i. Reemplazarlos?")) return false;
        try {
            saveRepository(repo_, path);
            directory_ = path;
            demo_ = false;
            std::cout << "Guardado en " << path.string() << '\n';
            return true;
        } catch (const std::exception& error) {
            std::cout << "No se pudo guardar: " << error.what() << '\n';
            return false;
        }
    }
    bool save(bool askPath = false) {
        if (askPath || directory_.empty() || demo_) {
            const std::string text = ask("Carpeta de destino (vacio = cancelar): ");
            if (text.empty()) return false;
            return saveTo(pathFromUtf8(text));
        }
        return saveTo(directory_);
    }
    bool mayReplace() {
        if (!repo_.dirty()) return true;
        while (true) {
            const std::string answer = lowercase(ask("Cambios sin guardar: [g]uardar, [d]escartar, [c]ancelar: "));
            if (answer == "g") return save();
            if (answer == "d") return true;
            if (answer == "c" || answer.empty()) return false;
        }
    }
    void load(const fs::path& path) {
        try {
            Repository fresh = loadRepository(path);
            repo_ = std::move(fresh);
            demo_ = samePath(path, demoPath_);
            directory_ = demo_ ? fs::path{} : path;
            std::cout << "Cargado: " << path.string();
            if (demo_) std::cout << " (demostracion; guarde una copia)";
            std::cout << '\n';
        } catch (const std::exception& error) {
            std::cout << "No se pudo cargar: " << error.what() << '\n';
            const fs::path backup = path / ".backup";
            if (fs::exists(backup / "manifest.csv") && confirm("Abrir la copia anterior .backup?")) {
                try {
                    Repository recovered = loadRepository(backup);
                    repo_ = std::move(recovered);
                    directory_.clear();
                    demo_ = false;
                    std::cout << "Copia abierta; use Guardar como para recuperarla.\n";
                } catch (const std::exception& backupError) {
                    std::cout << "La copia anterior tampoco se pudo abrir: "
                              << backupError.what() << '\n';
                }
            }
        }
    }
    void filesMenu() {
        while (true) {
            std::cout << "\n=== Datos ===\n"
                      << "Carpeta: " << (directory_.empty() ? "(sin guardar)" : directory_.string()) << '\n'
                      << "1. Iniciar vacio  2. Abrir carpeta  3. Cargar demostracion\n"
                      << "4. Guardar  5. Guardar como  0. Volver\n";
            const int option = askNumber("Opcion: ", 0, 5);
            if (option == 0) return;
            try {
                if (option == 4) save();
                else if (option == 5) save(true);
                else if (mayReplace()) {
                    if (option == 1) {
                        repo_ = Repository();
                        directory_.clear();
                        demo_ = false;
                        std::cout << "Espacio vacio creado.\n";
                    } else if (option == 2) {
                        const std::string text = ask("Carpeta con manifest.csv: ");
                        if (!text.empty()) load(pathFromUtf8(text));
                    } else if (option == 3) {
                        if (demoPath_.empty()) std::cout << "No se encontro data/demo.\n";
                        else load(demoPath_);
                    }
                }
            } catch (const std::exception& error) {
                std::cout << "Error: " << error.what() << '\n';
            }
        }
    }
    void importMenu() {
        std::cout << "\n=== Importar CSV ===\n";
        for (std::size_t i = 0; i < ALL_KINDS.size(); ++i)
            std::cout << i + 1 << ". " << ALL_KINDS[i] << '\n';
        std::cout << "0. Cancelar\n";
        const int option = askNumber("Tipo: ", 0, 7);
        if (option == 0) return;
        const std::string kind = ALL_KINDS[static_cast<std::size_t>(option - 1)];
        const std::string text = ask("Archivo CSV: ");
        if (text.empty()) return;
        const fs::path path = pathFromUtf8(text);
        const ImportResult preview = importCsv(repo_, path, kind, false);
        std::cout << "Filas: " << preview.total << " | Aceptables: " << preview.accepted
                  << " | Rechazadas: " << preview.total - preview.accepted << '\n';
        for (std::size_t i = 0; i < preview.errors.size() && i < 15; ++i)
            std::cout << "- " << preview.errors[i] << '\n';
        if (preview.accepted && confirm("Importar las aceptables?")) {
            const ImportResult done = importCsv(repo_, path, kind, true);
            std::cout << "Importadas: " << done.accepted << '\n';
        }
    }
public:
    void startup(const std::optional<fs::path>& initial, bool demoFlag) {
        if (demoFlag && !demoPath_.empty()) { load(demoPath_); return; }
        if (initial && fs::exists(*initial / "manifest.csv")) { load(*initial); return; }
        std::cout << "PEA-i UPC - inicio\n"
                  << "1. Iniciar vacio  2. Abrir carpeta  3. Cargar demostracion  0. Salir\n";
        const int option = askNumber("Opcion: ", 0, 3);
        if (option == 0) throw EndInput{};
        if (option == 2) {
            const std::string text = ask("Carpeta con manifest.csv: ");
            if (!text.empty()) load(pathFromUtf8(text));
        } else if (option == 3) {
            if (demoPath_.empty()) std::cout << "No se encontro data/demo. Iniciando vacio.\n";
            else load(demoPath_);
        } else std::cout << "Espacio vacio.\n";
    }
    void run() {
        while (true) {
            std::cout << "\n=== PEA-i UPC | C++ ==="
                      << (repo_.dirty() ? "  * sin guardar" : "") << '\n'
                      << "1. Grupos  2. Investigadores  3. Productos  4. Planes\n"
                      << "5. Relaciones  6. Importar CSV  7. Estadisticas\n"
                      << "8. Cola de revision  9. Deshacer  10. Datos  11. Guardar  0. Salir\n";
            const int option = askNumber("Opcion: ", 0, 11);
            if (option == 0) {
                if (mayReplace()) return;
                continue;
            }
            try {
                if (option >= 1 && option <= 4)
                    recordMenu(repo_, ENTITY_KINDS[static_cast<std::size_t>(option - 1)]);
                else if (option == 5) relationMenu(repo_);
                else if (option == 6) importMenu();
                else if (option == 7) statisticsMenu(repo_);
                else if (option == 8) queueMenu(repo_);
                else if (option == 9)
                    std::cout << (repo_.undo() ? "Ultima accion deshecha.\n" : "Historial vacio.\n");
                else if (option == 10) filesMenu();
                else if (option == 11) save();
            } catch (const std::exception& error) {
                std::cout << "Error: " << error.what() << '\n';
            }
        }
    }
};

// Protocolo local: una solicitud JSON por linea en stdin y una respuesta en stdout.
// Los valores de la solicitud son cadenas; "values" contiene otro objeto JSON
// codificado como cadena. Esto permite reutilizar el lector de instantaneas.
std::string jsonRow(const Row& row) {
    std::string result = "{";
    bool first = true;
    for (const auto& item : row) {
        if (!first) result.push_back(',');
        first = false;
        result += jsonString(item.first) + ":" + jsonString(item.second);
    }
    return result + "}";
}
std::string jsonRows(const Rows& rows) {
    std::string result = "[";
    bool first = true;
    for (const Row& row : rows) {
        if (!first) result.push_back(',');
        first = false;
        result += jsonRow(row);
    }
    return result + "]";
}
std::string jsonPage(const Page& page) {
    return "{\"rows\":" + jsonRows(page.rows) +
           ",\"total\":" + std::to_string(page.total) + "}";
}
std::string jsonTally(const std::map<std::string, int>& tally) {
    std::string result = "{";
    bool first = true;
    for (const auto& item : tally) {
        if (!first) result.push_back(',');
        first = false;
        result += jsonString(item.first) + ":" + std::to_string(item.second);
    }
    return result + "}";
}
std::string jsonStatistics(const Statistics& value) {
    return "{\"productos\":" + jsonRows(value.products) +
           ",\"total\":" + std::to_string(value.total) +
           ",\"por_anio\":" + jsonTally(value.byYear) +
           ",\"por_tipologia\":" + jsonTally(value.byType) +
           ",\"por_categoria\":" + jsonTally(value.byCategory) +
           ",\"por_validacion\":" + jsonTally(value.byValidation) + "}";
}
std::string jsonImport(const ImportResult& value) {
    std::string errors = "[";
    for (std::size_t i = 0; i < value.errors.size(); ++i) {
        if (i) errors.push_back(',');
        errors += jsonString(value.errors[i]);
    }
    return "{\"total\":" + std::to_string(value.total) +
           ",\"accepted\":" + std::to_string(value.accepted) +
           ",\"errors\":" + errors + "]}";
}
std::optional<int> optionalYear(const Row& request, const std::string& name) {
    const std::string value = field(request, name);
    if (value.empty()) return std::nullopt;
    if (!digits(value)) throw DataError("Anio invalido");
    try {
        const int year = std::stoi(value);
        if (year < 1900 || year > currentYear() + 1) throw DataError("Anio fuera de rango");
        return year;
    } catch (const std::out_of_range&) {
        throw DataError("Anio fuera de rango");
    }
}
std::size_t pageNumber(const Row& request, const std::string& name,
                       std::size_t fallback, std::size_t maximum) {
    const std::string value = field(request, name);
    if (value.empty()) return fallback;
    if (!digits(value)) throw DataError("Paginacion invalida");
    try {
        const auto parsed = std::stoull(value);
        if (parsed > maximum) throw DataError("Paginacion fuera de rango");
        return static_cast<std::size_t>(parsed);
    } catch (const std::out_of_range&) {
        throw DataError("Paginacion fuera de rango");
    }
}
class ApiApp {
    Repository repo_;
    bool stopping_ = false;

    std::string state() const {
        return "{\"dirty\":" + std::string(repo_.dirty() ? "true" : "false") +
               ",\"history_size\":" + std::to_string(repo_.historySize()) +
               ",\"queue_size\":" + std::to_string(repo_.queueSize()) + "}";
    }
    std::string execute(const Row& request) {
        const std::string action = field(request, "action");
        const std::string kind = field(request, "kind");
        const std::string key = field(request, "key");
        const std::string second = field(request, "second");
        if (action == "ping") return "{\"backend\":\"cpp\",\"protocol\":\"1\"}";
        if (action == "state") return state();
        if (action == "new_id") {
            if (entityIndex(kind) < 0) throw DataError("Tipo de entidad desconocido");
            return jsonString(newId(kind));
        }
        if (action == "shutdown") { stopping_ = true; return "null"; }
        if (action == "reset") { repo_ = Repository(); return "null"; }
        if (action == "load") {
            const fs::path path = pathFromUtf8(field(request, "path"));
            if (path.empty()) throw DataError("Falta carpeta de datos");
            Repository fresh = loadRepository(path);
            repo_ = std::move(fresh);
            return "null";
        }
        if (action == "save") {
            const fs::path path = pathFromUtf8(field(request, "path"));
            if (path.empty()) throw DataError("Falta carpeta de destino");
            if (samePath(path, projectDemo())) throw DataError("La demostracion es de solo lectura");
            saveRepository(repo_, path);
            return "null";
        }
        if (action == "rows") return jsonRows(repo_.rows(kind));
        if (action == "page")
            return jsonPage(repo_.page(kind, pageNumber(request, "offset", 0, SIZE_MAX),
                                      pageNumber(request, "limit", 100, 200), field(request, "query")));
        if (action == "summary") {
            const auto counts = repo_.activeCounts();
            const auto categories = repo_.statistics("Todos", "", {}, {}, "", "", 0, 0).byCategory;
            return "{\"active_groups\":" + std::to_string(counts.first) +
                   ",\"active_people\":" + std::to_string(counts.second) +
                   ",\"categories\":" + jsonTally(categories) + "}";
        }
        if (action == "get") {
            if (!FIELDS.count(kind)) throw DataError("Tipo desconocido");
            const Row* row = repo_.get(kind, key, second);
            return row ? jsonRow(*row) : "null";
        }
        if (action == "related") {
            const std::string side = field(request, "side");
            if (side != "left" && side != "right") throw DataError("Extremo desconocido");
            return jsonRows(repo_.related(kind, key, side == "left"));
        }
        if (action == "related_page") {
            const std::string side = field(request, "side");
            if (side != "left" && side != "right") throw DataError("Extremo desconocido");
            return jsonPage(repo_.relatedPage(kind, key, side == "left",
                        pageNumber(request, "offset", 0, SIZE_MAX),
                        pageNumber(request, "limit", 100, 200), field(request, "active") == "1"));
        }
        if (action == "create" || action == "update") {
            const Row values = SnapshotParser(field(request, "values")).parseRow();
            if (action == "create") {
                repo_.create(kind, values);
                const Row* row = repo_.get(kind, field(values, entityIndex(kind) >= 0 ? "id" : RELATION_ENDS.at(kind)[0]),
                                           entityIndex(kind) >= 0 ? "" : field(values, RELATION_ENDS.at(kind)[1]));
                return row ? jsonRow(*row) : "null";
            }
            repo_.update(kind, key, second, values);
            return jsonRow(*repo_.get(kind, key, second));
        }
        if (action == "delete") { repo_.erase(kind, key, second); return "null"; }
        if (action == "toggle") { repo_.toggle(kind, key, second); return "null"; }
        if (action == "statistics") {
            return jsonStatistics(repo_.statistics(
                field(request, "view"), field(request, "selected"),
                optionalYear(request, "start"), optionalYear(request, "end"),
                field(request, "category"), field(request, "status"),
                pageNumber(request, "offset", 0, SIZE_MAX),
                pageNumber(request, "limit", 100, 200)));
        }
        if (action == "queue_rows") return jsonRows(repo_.queueRows());
        if (action == "queue_page")
            return jsonPage(repo_.queuePage(pageNumber(request, "offset", 0, SIZE_MAX),
                                            pageNumber(request, "limit", 100, 200)));
        if (action == "queue_front") {
            const auto job = repo_.queueFront();
            return job ? jsonRow(*job) : "null";
        }
        if (action == "enqueue_review") {
            repo_.enqueueReview(field(request, "product_id"), field(request, "reason"));
            return "null";
        }
        if (action == "process_review")
            return jsonRow(repo_.processReview(field(request, "status"), field(request, "observation")));
        if (action == "discard_review") return jsonRow(repo_.discardReview());
        if (action == "undo") return repo_.undo() ? "true" : "false";
        if (action == "clear_history") { repo_.clearHistory(); return "null"; }
        if (action == "preview_csv" || action == "import_csv") {
            return jsonImport(importCsv(repo_, pathFromUtf8(field(request, "path")), kind,
                                        action == "import_csv"));
        }
        throw DataError("Accion de protocolo desconocida: " + action);
    }
public:
    void startup(const std::optional<fs::path>& initial, bool demo) {
        if (demo) {
            const fs::path path = projectDemo();
            if (path.empty()) throw DataError("No se encontro data/demo");
            repo_ = loadRepository(path);
        } else if (initial) {
            repo_ = loadRepository(*initial);
        }
    }
    void run() {
        std::string line;
        while (!stopping_ && std::getline(std::cin, line)) {
            try {
                const Row request = SnapshotParser(line).parseRow();
                const std::string result = execute(request);
                std::cout << "{\"ok\":true,\"result\":" << result
                          << ",\"state\":" << state() << "}\n" << std::flush;
            } catch (const std::bad_alloc&) {
                std::cout << "{\"ok\":false,\"error\":\"Memoria insuficiente para completar la operacion\""
                          << ",\"state\":" << state() << "}\n" << std::flush;
            } catch (const std::exception& error) {
                std::cout << "{\"ok\":false,\"error\":" << jsonString(error.what())
                          << ",\"state\":" << state() << "}\n" << std::flush;
            }
        }
    }
};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("Autoprueba: " + message);
}
void selfTest(const fs::path& demo) {
    DoublyList list;
    require(list.rows().empty(), "lista vacia");
    list.append({{"id", "A"}});
    list.append({{"id", "B"}});
    list.append({{"id", "C"}});
    require(field(list.backwards().front(), "id") == "C", "recorrido inverso");
    list.erase("A");
    list.erase("C");
    list.erase("B");
    require(list.size() == 0, "eliminar extremos y centro");
    MultiList links("grupo_id", "investigador_id");
    links.add({{"grupo_id", "G1"}, {"investigador_id", "I1"}});
    links.add({{"grupo_id", "G1"}, {"investigador_id", "I2"}});
    links.add({{"grupo_id", "G2"}, {"investigador_id", "I1"}});
    require(links.byLeft("G1").size() == 2 && links.byRight("I1").size() == 2,
            "multilista en dos direcciones");
    links.erase("G1", "I1");
    require(links.byLeft("G1").size() == 1 && links.byRight("I1").size() == 1,
            "desvincular multilista");
    LinkedStack stack;
    stack.push("A");
    stack.push("B");
    require(stack.pop() == "B" && stack.pop() == "A", "pila LIFO");
    LinkedQueue queue;
    queue.enqueue({{"id", "A"}});
    queue.enqueue({{"id", "B"}});
    require(field(*queue.dequeue(), "id") == "A" &&
            field(*queue.dequeue(), "id") == "B", "cola FIFO");

    Repository repo = loadRepository(demo);
    require(repo.statistics().products.size() == 4, "total demo sin duplicados");
    require(repo.statistics("Todos", "", 2025, 2026).products.size() == 2, "ventana de dos anios");
    require(repo.statistics("Todos", "", 2022, 2026).products.size() == 3, "ventana de cinco anios");
    require(repo.statistics("Grupo", "G-DEMO-1").products.size() == 3, "vista por grupo");
    require(repo.statistics("Investigador", "I-DEMO-2").products.size() == 2, "vista por investigador");
    require(repo.statistics("Todos", "", {}, {}, "Ejemplo A").products.size() == 1,
            "filtro de categoria");
    require(repo.queueSize() == 2 && field(*repo.queueFront(), "producto_id") == "P-DEMO-2",
            "cola persistida");
    repo.toggle("grupos_productos", "G-DEMO-1", "P-DEMO-1");
    require(repo.statistics("Grupo", "G-DEMO-1").products.size() == 2,
            "vinculo inactivo fuera de la vista");
    require(repo.undo() && repo.statistics("Grupo", "G-DEMO-1").products.size() == 3,
            "deshacer vinculo");
    try {
        repo.create("productos", {{"id", "P-INVALIDO"}, {"titulo", "Anio imposible"},
                                  {"anio", "1800"}});
        throw std::runtime_error("No se valido el anio");
    } catch (const DataError&) {}
    try {
        repo.create("autorias", {{"producto_id", "P-DEMO-1"}, {"investigador_id", "I-NOEXISTE"}});
        throw std::runtime_error("No se valido la referencia");
    } catch (const DataError&) {}
    try {
        repo.erase("grupos", "G-DEMO-1");
        throw std::runtime_error("No se bloqueo el borrado con relaciones");
    } catch (const DataError&) {}
    repo.update("productos", "P-DEMO-1", "",
                {{"categoria", "Categoria revisada"}, {"observacion", "Nueva evidencia"}});
    require(field(*repo.get("productos", "P-DEMO-1"), "categoria") == "Categoria revisada",
            "editar categoria");
    require(repo.undo(), "deshacer disponible");
    require(field(*repo.get("productos", "P-DEMO-1"), "categoria") == "Ejemplo A",
            "deshacer categoria");
    repo.enqueueReview("P-DEMO-4", "Otra revision");
    require(repo.queueSize() == 3, "encolar");
    require(repo.undo() && repo.queueSize() == 2, "deshacer cola");

    const auto tick = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    StagingFolder temp(fs::temp_directory_path() / ("pea-cpp-test-" + std::to_string(tick)));
    repo.update("productos", "P-DEMO-2", "",
                {{"validacion", "validado"}, {"observacion", "Revision de prueba"}});
    saveRepository(repo, temp.path);
    Repository loaded = loadRepository(temp.path);
    require(loaded.snapshot() == repo.snapshot(), "CSV y JSON de historial ida y vuelta");
    require(loaded.undo(), "historial cargado");
    require(field(*loaded.get("productos", "P-DEMO-2"), "validacion") == "pendiente",
            "deshacer tras reinicio");

    Repository extra;
    extra.create("productos", {{"id", "P-TEXTO"}, {"titulo", "Tildes: acción, comas\nsegunda linea"},
                               {"anio", "2025"}}, false);
    saveRepository(extra, temp.path / "especial");
    Repository again = loadRepository(temp.path / "especial");
    require(field(*again.get("productos", "P-TEXTO"), "titulo") ==
            "Tildes: acción, comas\nsegunda linea", "CSV UTF-8 multilinea");
    Rows imported = {
        {{"id", "P-IMPORT"}, {"titulo", "Importado"}, {"anio", "2026"}},
        {{"id", "P-TEXTO"}, {"titulo", "Duplicado"}, {"anio", "2026"}}
    };
    Rows completed;
    for (const Row& row : imported) completed.push_back(cleanRow("productos", row));
    const fs::path importPath = temp.path / "import.csv";
    writeCsv(importPath, FIELDS.at("productos"), completed);
    ImportResult preview = importCsv(again, importPath, "productos", false);
    require(preview.total == 2 && preview.accepted == 1 && preview.errors.size() == 1 &&
            !again.get("productos", "P-IMPORT"), "vista previa CSV sin mutacion");
    ImportResult applied = importCsv(again, importPath, "productos", true);
    require(applied.accepted == 1 && again.get("productos", "P-IMPORT"),
            "importacion CSV parcial");
    require(again.undo() && !again.get("productos", "P-IMPORT"), "deshacer importacion");
    std::cout << "Autoprueba C++ correcta: estructuras, vistas, integridad, CSV y persistencia.\n";
}

} // namespace pea

int main(int argc, char* argv[]) {
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif
    try {
        std::optional<pea::fs::path> directory;
        bool demo = false;
        bool check = false;
        bool api = false;
        pea::fs::path testData;
        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];
            if (arg == "--help" || arg == "-h") {
                std::cout << "PEA-i UPC C++17\n"
                          << "Uso: pea_cpp [--data-dir CARPETA] [--demo] [--api]\n"
                          << "     pea_cpp --self-test [CARPETA_DEMO]\n"
                          << "El programa gestiona datos CSV con menus de consola o protocolo JSON.\n";
                return 0;
            }
            if (arg == "--data-dir" && i + 1 < argc) directory = pea::pathFromUtf8(argv[++i]);
            else if (arg == "--demo") demo = true;
            else if (arg == "--api") api = true;
            else if (arg == "--self-test") {
                check = true;
                if (i + 1 < argc && argv[i + 1][0] != '-') testData = pea::pathFromUtf8(argv[++i]);
            } else {
                std::cerr << "Argumento desconocido o incompleto: " << arg << '\n';
                return 2;
            }
        }
        if (check) {
            if (testData.empty()) testData = pea::projectDemo();
            if (testData.empty()) throw pea::DataError("No se encontro data/demo");
            pea::selfTest(testData);
            return 0;
        }
        if (api) {
            pea::ApiApp app;
            app.startup(directory, demo);
            app.run();
            return 0;
        }
        pea::ConsoleApp app;
        app.startup(directory, demo);
        app.run();
        return 0;
    } catch (const pea::EndInput&) {
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
