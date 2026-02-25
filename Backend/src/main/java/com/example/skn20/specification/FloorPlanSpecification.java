package com.example.skn20.specification;

import com.example.skn20.entity.FloorPlan;
import com.example.skn20.entity.FloorplanAnalysis;
import jakarta.persistence.criteria.*;
import org.springframework.data.jpa.domain.Specification;

import java.time.LocalDate;
import java.time.LocalTime;

public class FloorPlanSpecification {

    public static Specification<FloorPlan> nameLike(String name) {
        return (root, query, cb) -> {
            if (name == null || name.isEmpty()) return null;
            return cb.like(cb.lower(root.get("name")), "%" + name.toLowerCase() + "%");
        };
    }

    public static Specification<FloorPlan> uploaderEmailLike(String email) {
        return (root, query, cb) -> {
            if (email == null || email.isEmpty()) return null;
            return cb.like(cb.lower(root.get("user").get("email")), "%" + email.toLowerCase() + "%");
        };
    }

    public static Specification<FloorPlan> createdAfter(LocalDate startDate) {
        return (root, query, cb) -> {
            if (startDate == null) return null;
            return cb.greaterThanOrEqualTo(root.get("createdAt"), startDate.atStartOfDay());
        };
    }

    public static Specification<FloorPlan> createdBefore(LocalDate endDate) {
        return (root, query, cb) -> {
            if (endDate == null) return null;
            return cb.lessThanOrEqualTo(root.get("createdAt"), endDate.atTime(LocalTime.MAX));
        };
    }

    public static Specification<FloorPlan> roomCountBetween(Integer min, Integer max) {
        return (root, query, cb) -> {
            if (min == null && max == null) return null;

            Subquery<Long> subquery = query.subquery(Long.class);
            Root<FloorplanAnalysis> analysisRoot = subquery.from(FloorplanAnalysis.class);
            subquery.select(analysisRoot.get("floorPlan").get("id"));

            Predicate roomPredicate = cb.conjunction();
            if (min != null) {
                roomPredicate = cb.and(roomPredicate,
                        cb.greaterThanOrEqualTo(analysisRoot.get("roomCount"), min));
            }
            if (max != null) {
                roomPredicate = cb.and(roomPredicate,
                        cb.lessThanOrEqualTo(analysisRoot.get("roomCount"), max));
            }
            subquery.where(roomPredicate);

            return root.get("id").in(subquery);
        };
    }
}
